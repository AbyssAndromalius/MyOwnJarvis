package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	// Load configuration
	cfg, err := LoadConfig("config.yaml")
	if err != nil {
		log.Printf("Warning: Failed to load config.yaml: %v", err)
		log.Println("Using default configuration")
		cfg = &Config{}
		cfg.Server.Host = "127.0.0.1"
		cfg.Server.Port = 10090
		cfg.Orchestrator.URL = "http://localhost:10080"
		cfg.Orchestrator.TimeoutSeconds = 60
		cfg.Session.MaxHistory = 20
		cfg.TTS.Enabled = true
	}

	// Create server
	server, err := NewServer(cfg)
	if err != nil {
		log.Fatalf("Failed to create server: %v", err)
	}

	// Start session cleanup routine
	server.StartCleanupRoutine()

	// Setup HTTP routes
	mux := http.NewServeMux()
	mux.HandleFunc("/", server.IndexHandler)
	mux.HandleFunc("/api/voice", server.VoiceHandler)
	mux.HandleFunc("/api/chat", server.ChatHandler)
	mux.HandleFunc("/api/health", server.HealthHandler)
	mux.HandleFunc("/api/clear-history", server.ClearHistoryHandler)

	// Create HTTP server
	addr := fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port)
	httpServer := &http.Server{
		Addr:         addr,
		Handler:      mux,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 90 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Channel to listen for interrupt signals
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	// Start server in a goroutine
	go func() {
		log.Printf("Starting Windows Go Client on %s", addr)
		log.Printf("Orchestrator URL: %s", cfg.Orchestrator.URL)
		log.Printf("Open http://%s in Microsoft Edge to use the assistant", addr)
		
		// Check orchestrator health on startup
		err := server.proxy.CheckHealth()
		if err != nil {
			log.Printf("WARNING: Orchestrator is not reachable at %s", cfg.Orchestrator.URL)
			log.Printf("         The client will start anyway, but voice/chat features won't work until the orchestrator is available")
			log.Printf("         Error: %v", err)
		} else {
			log.Printf("Orchestrator health check passed")
		}
		
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for interrupt signal
	<-stop
	log.Println("\nShutting down gracefully...")

	// Create shutdown context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Shutdown server
	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("Server shutdown error: %v", err)
	}

	log.Println("Server stopped")
}
