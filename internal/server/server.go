package server

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"time"

	"github.com/assistant/orchestrator/internal/clients"
	"github.com/assistant/orchestrator/internal/config"
	"github.com/assistant/orchestrator/internal/handlers"
)

// Server represents the HTTP server
type Server struct {
	httpServer *http.Server
	logger     *slog.Logger
}

// New creates a new HTTP server with configured routes and middleware
func New(cfg *config.Config, logger *slog.Logger) *Server {
	// Create sidecar clients
	voiceClient := clients.NewVoiceClient(
		cfg.Sidecars.VoiceURL,
		cfg.Sidecars.GetSidecarTimeout(),
	)

	llmClient := clients.NewLLMClient(
		cfg.Sidecars.LLMURL,
		cfg.Sidecars.GetSidecarTimeout(),
	)

	learningClient := clients.NewLearningClient(
		cfg.Sidecars.LearningURL,
		cfg.Sidecars.GetSidecarTimeout(),
	)

	// Create handlers
	chatHandler := handlers.NewChatHandler(llmClient, cfg, logger)
	voiceHandler := handlers.NewVoiceHandler(voiceClient, llmClient, logger)
	learnHandler := handlers.NewLearnHandler(learningClient, cfg, logger)
	healthHandler := handlers.NewHealthHandler(voiceClient, llmClient, learningClient, logger)

	// Setup routes
	mux := http.NewServeMux()
	mux.Handle("/chat", loggingMiddleware(logger, chatHandler))
	mux.Handle("/voice", loggingMiddleware(logger, voiceHandler))
	mux.Handle("/learn", loggingMiddleware(logger, learnHandler))
	mux.Handle("/health", loggingMiddleware(logger, healthHandler))

	// Create HTTP server
	httpServer := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Server.Port),
		Handler:      mux,
		ReadTimeout:  cfg.Server.GetReadTimeout(),
		WriteTimeout: cfg.Server.GetWriteTimeout(),
	}

	return &Server{
		httpServer: httpServer,
		logger:     logger,
	}
}

// Start starts the HTTP server
func (s *Server) Start() error {
	s.logger.Info("starting server", "addr", s.httpServer.Addr)
	return s.httpServer.ListenAndServe()
}

// Shutdown gracefully shuts down the server
func (s *Server) Shutdown(ctx context.Context) error {
	s.logger.Info("shutting down server")
	return s.httpServer.Shutdown(ctx)
}

// loggingMiddleware logs incoming HTTP requests
func loggingMiddleware(logger *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		// Create a response writer wrapper to capture status code
		rw := &responseWriter{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
		}

		// Call the next handler
		next.ServeHTTP(rw, r)

		// Log request
		duration := time.Since(start)
		logger.Info("request completed",
			"method", r.Method,
			"path", r.URL.Path,
			"status", rw.statusCode,
			"duration_ms", duration.Milliseconds(),
			"remote_addr", r.RemoteAddr,
		)
	})
}

// responseWriter wraps http.ResponseWriter to capture the status code
type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

// WriteHeader captures the status code
func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}
