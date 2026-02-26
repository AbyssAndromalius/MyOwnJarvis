package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/assistant/orchestrator/internal/config"
	"github.com/assistant/orchestrator/internal/server"
)

func main() {
	// Setup structured logging
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	// Load configuration
	cfg, err := config.Load("config.yaml")
	if err != nil {
		logger.Error("failed to load configuration", "error", err)
		os.Exit(1)
	}

	logger.Info("configuration loaded", 
		"port", cfg.Server.Port,
		"voice_url", cfg.Sidecars.VoiceURL,
		"llm_url", cfg.Sidecars.LLMURL,
		"learning_url", cfg.Sidecars.LearningURL,
	)

	// Create and start server
	srv := server.New(cfg, logger)

	// Channel to listen for errors from the server
	serverErrors := make(chan error, 1)

	// Start server in a goroutine
	go func() {
		logger.Info("server starting", "port", cfg.Server.Port)
		serverErrors <- srv.Start()
	}()

	// Channel to listen for interrupt signals
	shutdown := make(chan os.Signal, 1)
	signal.Notify(shutdown, os.Interrupt, syscall.SIGTERM)

	// Block until we receive a signal or an error
	select {
	case err := <-serverErrors:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("server error", "error", err)
			os.Exit(1)
		}

	case sig := <-shutdown:
		logger.Info("shutdown signal received", "signal", sig)

		// Give outstanding requests a deadline for completion
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()

		// Gracefully shutdown the server
		if err := srv.Shutdown(ctx); err != nil {
			logger.Error("graceful shutdown failed", "error", err)
			
			// Force shutdown if graceful fails
			if err := srv.Shutdown(context.Background()); err != nil {
				logger.Error("forced shutdown failed", "error", err)
			}
		}

		logger.Info("server stopped")
	}
}
