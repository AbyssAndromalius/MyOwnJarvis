package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestHealthHandler_AllHealthy(t *testing.T) {
	// Create mock clients - all healthy
	mockVoice := &mockVoiceClient{
		healthFunc: func(ctx context.Context) (time.Duration, error) {
			return 12 * time.Millisecond, nil
		},
	}

	mockLLM := &mockLLMClient{
		healthFunc: func(ctx context.Context) (time.Duration, error) {
			return 8 * time.Millisecond, nil
		},
	}

	mockLearning := &mockLearningClient{
		healthFunc: func(ctx context.Context) (time.Duration, error) {
			return 5 * time.Millisecond, nil
		},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewHealthHandler(mockVoice, mockLLM, mockLearning, logger)

	// Create request
	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp healthResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	// Check overall status
	if resp.Status != "ok" {
		t.Errorf("expected status 'ok', got %s", resp.Status)
	}

	// Check individual sidecar statuses
	if resp.Sidecars["voice"].Status != "ok" {
		t.Errorf("expected voice status 'ok', got %s", resp.Sidecars["voice"].Status)
	}
	if resp.Sidecars["llm"].Status != "ok" {
		t.Errorf("expected llm status 'ok', got %s", resp.Sidecars["llm"].Status)
	}
	if resp.Sidecars["learning"].Status != "ok" {
		t.Errorf("expected learning status 'ok', got %s", resp.Sidecars["learning"].Status)
	}

	// Check latencies are present
	if resp.Sidecars["voice"].LatencyMs == 0 {
		t.Error("expected voice latency > 0")
	}
}

func TestHealthHandler_Degraded(t *testing.T) {
	// Create mock clients - one unhealthy
	mockVoice := &mockVoiceClient{
		healthFunc: func(ctx context.Context) (time.Duration, error) {
			return 0, fmt.Errorf("voice unavailable")
		},
	}

	mockLLM := &mockLLMClient{
		healthFunc: func(ctx context.Context) (time.Duration, error) {
			return 8 * time.Millisecond, nil
		},
	}

	mockLearning := &mockLearningClient{
		healthFunc: func(ctx context.Context) (time.Duration, error) {
			return 5 * time.Millisecond, nil
		},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewHealthHandler(mockVoice, mockLLM, mockLearning, logger)

	// Create request
	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response - still 200 OK
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp healthResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	// Check overall status
	if resp.Status != "degraded" {
		t.Errorf("expected status 'degraded', got %s", resp.Status)
	}

	// Check voice is unreachable
	if resp.Sidecars["voice"].Status != "unreachable" {
		t.Errorf("expected voice status 'unreachable', got %s", resp.Sidecars["voice"].Status)
	}

	// Check other sidecars are ok
	if resp.Sidecars["llm"].Status != "ok" {
		t.Errorf("expected llm status 'ok', got %s", resp.Sidecars["llm"].Status)
	}
	if resp.Sidecars["learning"].Status != "ok" {
		t.Errorf("expected learning status 'ok', got %s", resp.Sidecars["learning"].Status)
	}
}

func TestHealthHandler_Error(t *testing.T) {
	// Create mock clients - all unhealthy
	mockVoice := &mockVoiceClient{
		healthFunc: func(ctx context.Context) (time.Duration, error) {
			return 0, fmt.Errorf("voice unavailable")
		},
	}

	mockLLM := &mockLLMClient{
		healthFunc: func(ctx context.Context) (time.Duration, error) {
			return 0, fmt.Errorf("llm unavailable")
		},
	}

	mockLearning := &mockLearningClient{
		healthFunc: func(ctx context.Context) (time.Duration, error) {
			return 0, fmt.Errorf("learning unavailable")
		},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewHealthHandler(mockVoice, mockLLM, mockLearning, logger)

	// Create request
	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response - still 200 OK (health endpoint never returns 503)
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp healthResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	// Check overall status
	if resp.Status != "error" {
		t.Errorf("expected status 'error', got %s", resp.Status)
	}

	// Check all sidecars are unreachable
	if resp.Sidecars["voice"].Status != "unreachable" {
		t.Errorf("expected voice status 'unreachable', got %s", resp.Sidecars["voice"].Status)
	}
	if resp.Sidecars["llm"].Status != "unreachable" {
		t.Errorf("expected llm status 'unreachable', got %s", resp.Sidecars["llm"].Status)
	}
	if resp.Sidecars["learning"].Status != "unreachable" {
		t.Errorf("expected learning status 'unreachable', got %s", resp.Sidecars["learning"].Status)
	}
}

func TestHealthHandler_MethodNotAllowed(t *testing.T) {
	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewHealthHandler(nil, nil, nil, logger)

	// Create POST request (should be GET)
	req := httptest.NewRequest("POST", "/health", nil)
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected status 405, got %d", w.Code)
	}
}
