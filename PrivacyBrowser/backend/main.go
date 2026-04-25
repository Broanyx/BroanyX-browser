// main.go
// -------
// PrivacyBrowser Go Proxy Engine
//
// A local HTTP/HTTPS proxy that:
//   1. Fetches EasyList on startup and builds a blocked-domain set
//   2. Intercepts every request: if domain is blocked → 403 immediately
//   3. For CONNECT tunnels (HTTPS): if not blocked → dials through Tor SOCKS5
//   4. For plain HTTP: if not blocked → fetches via Tor SOCKS5 and relays response
//
// Listens on:  127.0.0.1:8080
// Tor SOCKS5:  127.0.0.1:9050

package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"golang.org/x/net/proxy"
)

// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────

const (
	proxyListenAddr = "127.0.0.1:8080"
	torSOCKS5Addr   = "127.0.0.1:9050"

	// EasyList sources (two fetched in parallel; combined)
	easyListURL    = "https://easylist.to/easylist/easylist.txt"
	easyPrivacyURL = "https://easylist.to/easylist/easyprivacy.txt"

	// Refresh EasyList every 24 h (for long-running sessions)
	listRefreshInterval = 24 * time.Hour

	// Timeout for fetching ad lists (we don't go through Tor here — bootstrapping order)
	adListFetchTimeout = 60 * time.Second

	// Tunnel copy timeout after connect handshake established
	tunnelIOTimeout = 5 * time.Minute
)

// ─────────────────────────────────────────────────────────────────────────────
// AdBlocker
// ─────────────────────────────────────────────────────────────────────────────

// AdBlocker holds the blocked domain set and exposes thread-safe operations.
type AdBlocker struct {
	mu            sync.RWMutex
	blocked       map[string]struct{}
	blockedCount  atomic.Int64
	ready         atomic.Bool
}

// NewAdBlocker creates an AdBlocker and begins loading rules in the background.
func NewAdBlocker() *AdBlocker {
	ab := &AdBlocker{
		blocked: make(map[string]struct{}),
	}
	go ab.loadAndScheduleRefresh()
	return ab
}

// ShouldBlock returns true if the host (or any parent domain) is on the blocklist.
func (ab *AdBlocker) ShouldBlock(host string) bool {
	if !ab.ready.Load() {
		return false
	}
	host = strings.ToLower(strings.TrimSpace(host))
	// Strip port if present
	if h, _, err := net.SplitHostPort(host); err == nil {
		host = h
	}
	ab.mu.RLock()
	defer ab.mu.RUnlock()

	parts := strings.Split(host, ".")
	for i := 0; i < len(parts)-1; i++ {
		candidate := strings.Join(parts[i:], ".")
		if _, ok := ab.blocked[candidate]; ok {
			return true
		}
	}
	return false
}

// BlockedCount returns the total requests blocked so far.
func (ab *AdBlocker) BlockedCount() int64 {
	return ab.blockedCount.Load()
}

func (ab *AdBlocker) loadAndScheduleRefresh() {
	ab.fetch()
	ticker := time.NewTicker(listRefreshInterval)
	defer ticker.Stop()
	for range ticker.C {
		log.Println("[adblock] Refreshing EasyList…")
		ab.fetch()
	}
}

// fetch downloads both EasyList URLs concurrently and rebuilds the domain set.
func (ab *AdBlocker) fetch() {
	urls := []string{easyListURL, easyPrivacyURL}
	results := make([][]string, len(urls))
	var wg sync.WaitGroup

	// Use a plain http.Client (not through Tor) for bootstrapping ad lists
	client := &http.Client{Timeout: adListFetchTimeout}

	for i, u := range urls {
		wg.Add(1)
		go func(idx int, listURL string) {
			defer wg.Done()
			lines, err := fetchTextLines(client, listURL)
			if err != nil {
				log.Printf("[adblock] Failed to fetch %s: %v", listURL, err)
				return
			}
			log.Printf("[adblock] Downloaded %d lines from %s", len(lines), listURL)
			results[idx] = lines
		}(i, u)
	}
	wg.Wait()

	newBlocked := make(map[string]struct{}, 80000)
	for _, lines := range results {
		for _, line := range lines {
			domain, ok := parseEasyListDomain(line)
			if ok {
				newBlocked[domain] = struct{}{}
			}
		}
	}

	ab.mu.Lock()
	ab.blocked = newBlocked
	ab.mu.Unlock()
	ab.ready.Store(true)

	log.Printf("[adblock] ✅ Ready — %d blocked domains loaded.", len(newBlocked))
}

// fetchTextLines downloads a URL and returns its non-empty lines.
func fetchTextLines(client *http.Client, rawURL string) ([]string, error) {
	resp, err := client.Get(rawURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d from %s", resp.StatusCode, rawURL)
	}

	var lines []string
	scanner := bufio.NewScanner(resp.Body)
	// EasyList lines can be long; increase buffer
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" {
			lines = append(lines, line)
		}
	}
	return lines, scanner.Err()
}

// parseEasyListDomain extracts a plain domain from an EasyList rule like ||example.com^
func parseEasyListDomain(line string) (string, bool) {
	// Only handle simple domain-anchor rules: ||domain^
	if !strings.HasPrefix(line, "||") || !strings.HasSuffix(line, "^") {
		return "", false
	}
	domain := line[2 : len(line)-1]
	// Reject rules with paths, wildcards, or options
	if strings.ContainsAny(domain, "/*?$@") {
		return "", false
	}
	// Must look like a real domain (at least one dot)
	if !strings.Contains(domain, ".") {
		return "", false
	}
	return strings.ToLower(domain), true
}

// ─────────────────────────────────────────────────────────────────────────────
// Tor SOCKS5 dialer
// ─────────────────────────────────────────────────────────────────────────────

// newTorDialer returns a golang.org/x/net/proxy SOCKS5 dialer pointed at Tor.
func newTorDialer() (proxy.Dialer, error) {
	return proxy.SOCKS5("tcp", torSOCKS5Addr, nil, proxy.Direct)
}

// dialViaTor opens a TCP connection to addr through Tor.
func dialViaTor(dialer proxy.Dialer, addr string) (net.Conn, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	type result struct {
		conn net.Conn
		err  error
	}
	ch := make(chan result, 1)
	go func() {
		conn, err := dialer.Dial("tcp", addr)
		ch <- result{conn, err}
	}()
	select {
	case r := <-ch:
		return r.conn, r.err
	case <-ctx.Done():
		return nil, fmt.Errorf("tor dial timeout for %s", addr)
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// HTTP Proxy Handler
// ─────────────────────────────────────────────────────────────────────────────

// ProxyHandler implements http.Handler for both CONNECT and plain HTTP.
type ProxyHandler struct {
	adBlocker *AdBlocker
	torDialer proxy.Dialer
}

func (h *ProxyHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodConnect {
		h.handleCONNECT(w, r)
	} else {
		h.handleHTTP(w, r)
	}
}

// handleCONNECT handles HTTPS tunnels via CONNECT method.
func (h *ProxyHandler) handleCONNECT(w http.ResponseWriter, r *http.Request) {
	host := r.Host // e.g. "example.com:443"
	hostOnly, _, _ := net.SplitHostPort(host)
	if hostOnly == "" {
		hostOnly = host
	}

	if h.adBlocker.ShouldBlock(hostOnly) {
		h.adBlocker.blockedCount.Add(1)
		log.Printf("[block] CONNECT %s — blocked (ad/tracker)", host)
		http.Error(w, "Blocked by PrivacyBrowser Ad Blocker", http.StatusForbidden)
		return
	}

	// Dial target through Tor
	log.Printf("[tunnel] CONNECT %s → via Tor", host)
	targetConn, err := dialViaTor(h.torDialer, host)
	if err != nil {
		log.Printf("[error] Tor dial failed for %s: %v", host, err)
		http.Error(w, "Bad Gateway — Tor connection failed", http.StatusBadGateway)
		return
	}

	// Send 200 to client — tunnel established
	w.WriteHeader(http.StatusOK)

	// Hijack the client connection
	hijacker, ok := w.(http.Hijacker)
	if !ok {
		log.Println("[error] ResponseWriter does not support hijacking")
		targetConn.Close()
		return
	}
	clientConn, buf, err := hijacker.Hijack()
	if err != nil {
		log.Printf("[error] Hijack failed: %v", err)
		targetConn.Close()
		return
	}

	// Flush anything buffered from the hijack
	if buf.Reader.Buffered() > 0 {
		buffered, _ := io.ReadAll(buf.Reader)
		targetConn.Write(buffered)
	}

	// Bidirectional copy with timeouts
	go func() {
		defer clientConn.Close()
		defer targetConn.Close()
		pipe(clientConn, targetConn)
	}()
}

// handleHTTP proxies a plain HTTP request through Tor.
func (h *ProxyHandler) handleHTTP(w http.ResponseWriter, r *http.Request) {
	hostOnly := r.URL.Hostname()
	if hostOnly == "" {
		hostOnly = r.Host
	}

	if h.adBlocker.ShouldBlock(hostOnly) {
		h.adBlocker.blockedCount.Add(1)
		log.Printf("[block] HTTP %s %s — blocked (ad/tracker)", r.Method, r.URL)
		http.Error(w, "Blocked by PrivacyBrowser Ad Blocker", http.StatusForbidden)
		return
	}

	log.Printf("[proxy] HTTP %s %s → via Tor", r.Method, r.URL)

	// Build a transport that dials through Tor
	transport := &http.Transport{
		DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
			return dialViaTor(h.torDialer, addr)
		},
		DisableKeepAlives: true,
	}

	// Strip hop-by-hop headers
	outReq := r.Clone(r.Context())
	outReq.RequestURI = ""
	removeHopByHopHeaders(outReq.Header)

	// Make the request via Tor
	client := &http.Client{
		Transport: transport,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse // Don't follow redirects server-side
		},
	}

	resp, err := client.Do(outReq)
	if err != nil {
		log.Printf("[error] HTTP request via Tor failed: %v", err)
		http.Error(w, "Bad Gateway — Tor request failed", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	// Relay response headers
	removeHopByHopHeaders(resp.Header)
	for k, vv := range resp.Header {
		for _, v := range vv {
			w.Header().Add(k, v)
		}
	}
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

// ─────────────────────────────────────────────────────────────────────────────
// Utility helpers
// ─────────────────────────────────────────────────────────────────────────────

var hopByHopHeaders = []string{
	"Connection", "Proxy-Connection", "Keep-Alive", "Proxy-Authenticate",
	"Proxy-Authorization", "Te", "Trailers", "Transfer-Encoding", "Upgrade",
}

func removeHopByHopHeaders(h http.Header) {
	for _, k := range hopByHopHeaders {
		h.Del(k)
	}
}

// pipe copies data bidirectionally between two connections.
func pipe(a, b net.Conn) {
	done := make(chan struct{}, 2)
	copyConn := func(dst, src net.Conn) {
		io.Copy(dst, src)
		done <- struct{}{}
	}
	go copyConn(a, b)
	go copyConn(b, a)
	<-done // wait for either direction to finish, then close both
}

// hostFromRequest extracts the host from a URL (for plain HTTP requests).
func hostFromRequest(r *http.Request) string {
	if r.URL != nil && r.URL.Host != "" {
		return r.URL.Host
	}
	return r.Host
}

// ─────────────────────────────────────────────────────────────────────────────
// Status endpoint
// ─────────────────────────────────────────────────────────────────────────────

// statusHandler responds to GET http://localhost:8080/__proxy_status
func statusHandler(ab *AdBlocker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"running","tor_proxy":"%s","blocked_count":%d,"adblock_ready":%v}`,
			torSOCKS5Addr, ab.BlockedCount(), ab.ready.Load())
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────────

func main() {
	log.SetFlags(log.Ltime | log.Lshortfile)
	log.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	log.Println("  PrivacyBrowser Go Proxy Engine")
	log.Printf("  Listening:  %s", proxyListenAddr)
	log.Printf("  Tor SOCKS5: %s", torSOCKS5Addr)
	log.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

	// 1. Start ad-blocker (loads rules in background)
	ab := NewAdBlocker()

	// 2. Build Tor SOCKS5 dialer
	torDialer, err := newTorDialer()
	if err != nil {
		log.Fatalf("[fatal] Failed to create Tor SOCKS5 dialer: %v", err)
	}

	// 3. Build the mux: status endpoint + proxy catch-all
	mux := http.NewServeMux()
	mux.HandleFunc("/__proxy_status", statusHandler(ab))

	proxyHandler := &ProxyHandler{
		adBlocker: ab,
		torDialer: torDialer,
	}

	// Wrap mux so the proxy handler catches everything not matched by mux
	mainHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Status check (browser pings this to confirm proxy is alive)
		if r.URL != nil && r.URL.Path == "/__proxy_status" && r.Method == http.MethodGet {
			statusHandler(ab)(w, r)
			return
		}
		// If Host header signals it's a local management call, handle with mux
		host := r.Host
		if host == "localhost:8080" || host == "127.0.0.1:8080" {
			mux.ServeHTTP(w, r)
			return
		}
		proxyHandler.ServeHTTP(w, r)
	})

	// 4. Start listening
	server := &http.Server{
		Addr:         proxyListenAddr,
		Handler:      mainHandler,
		ReadTimeout:  2 * time.Minute,
		WriteTimeout: 5 * time.Minute,
		IdleTimeout:  5 * time.Minute,
	}

	log.Printf("[proxy] 🟢 Proxy server started on %s", proxyListenAddr)

	// Log env var that can signal shutdown
	_ = url.Parse // imported for helpers

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("[fatal] Server error: %v", err)
	}

	// Graceful shutdown on signal
	log.Println("[proxy] Proxy stopped.")
	os.Exit(0)
}
