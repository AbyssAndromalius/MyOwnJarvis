package handlers

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"sync"
	"time"

	"github.com/assistant/orchestrator/internal/clients"
)

// HealthHandler handles GET /health requests
type HealthHandler struct {
	voiceClient    clients.VoiceClientInterface
	llmClient      clients.LLMClientInterface
	learningClient clients.LearningClientInterface
	logger         *slog.Logger
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(
	voiceClient clients.VoiceClientInterface,
	llmClient clients.LLMClientInterface,
	learningClient clients.LearningClientInterface,
	logger *slog.Logger,
) *HealthHandler {
	return &HealthHandler{
		voiceClient:   voiceClient,
		llmClient:     llmClient,
		learningClient: learningClient,
		logger:        logger,
	}
}

// sidecarHealth represents the health status of a single sidecar
type sidecarHealth struct {
	Status     string `json:"status"`
	LatencyMs  int64  `json:"latency_ms,omitempty"`
}

// healthResponse represents the aggregated health response
type healthResponse struct {
	Status   string                   `json:"status"`
	Sidecars map[string]sidecarHealth `json:"sidecars"`
}

// ServeHTTP implements http.Handler
func (h *HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Only accept GET
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed", "")
		return
	}

	ctx := r.Context()

	// Channel to collect results
	type healthResult struct {
		name    string
		status  string
		latency time.Duration
	}
	results := make(chan healthResult, 3)

	// WaitGroup for parallel health checks
	var wg sync.WaitGroup
	wg.Add(3)

	// Check Voice sidecar
	go func() {
		defer wg.Done()
		latency, err := h.voiceClient.Health(ctx)
		status := "ok"
		if err != nil {
			h.logger.Warn("voice sidecar health check failed", "error", err)
			status = "unreachable"
		}
		results <- healthResult{name: "voice", status: status, latency: latency}
	}()

	// Check LLM sidecar
	go func() {
		defer wg.Done()
		latency, err := h.llmClient.Health(ctx)
		status := "ok"
		if err != nil {
			h.logger.Warn("llm sidecar health check failed", "error", err)
			status = "unreachable"
		}
		results <- healthResult{name: "llm", status: status, latency: latency}
	}()

	// Check Learning sidecar
	go func() {
		defer wg.Done()
		latency, err := h.learningClient.Health(ctx)
		status := "ok"
		if err != nil {
			h.logger.Warn("learning sidecar health check failed", "error", err)
			status = "unreachable"
		}
		results <- healthResult{name: "learning", status: status, latency: latency}
	}()

	// Wait for all health checks to complete
	go func() {
		wg.Wait()
		close(results)
	}()

	// Collect results
	sidecars := make(map[string]sidecarHealth)
	okCount := 0
	unreachableCount := 0

	for result := range results {
		health := sidecarHealth{
			Status: result.status,
		}
		
		if result.status == "ok" {
			health.LatencyMs = result.latency.Milliseconds()
			okCount++
		} else {
			unreachableCount++
		}

		sidecars[result.name] = health
	}

	// Determine overall status
	var overallStatus string
	if okCount == 3 {
		overallStatus = "ok"
	} else if unreachableCount == 3 {
		overallStatus = "error"
	} else {
		overallStatus = "degraded"
	}

	h.logger.Info("health check completed", 
		"status", overallStatus, 
		"ok_count", okCount, 
		"unreachable_count", unreachableCount)

	// Return health response (always 200 OK)
	response := healthResponse{
		Status:   overallStatus,
		Sidecars: sidecars,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
