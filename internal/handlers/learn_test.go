package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/assistant/orchestrator/internal/clients"
	"github.com/assistant/orchestrator/internal/config"
)

// mockLearningClient implements a mock Learning client for testing
type mockLearningClient struct {
	submitFunc func(ctx context.Context, req *clients.LearningRequest) (*clients.LearningResponse, error)
	healthFunc func(ctx context.Context) (time.Duration, error)
}

func (m *mockLearningClient) Submit(ctx context.Context, req *clients.LearningRequest) (*clients.LearningResponse, error) {
	if m.submitFunc != nil {
		return m.submitFunc(ctx, req)
	}
	return nil, nil
}

func (m *mockLearningClient) Health(ctx context.Context) (time.Duration, error) {
	if m.healthFunc != nil {
		return m.healthFunc(ctx)
	}
	return 0, nil
}

func TestLearnHandler_ValidRequest(t *testing.T) {
	// Create config
	cfg := &config.Config{
		ValidUserIDs: []string{"dad", "mom", "teen", "child"},
	}

	// Create mock Learning client
	mockClient := &mockLearningClient{
		submitFunc: func(ctx context.Context, req *clients.LearningRequest) (*clients.LearningResponse, error) {
			return &clients.LearningResponse{
				ID:     "uuid-456",
				Status: "processing",
			}, nil
		},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewLearnHandler(mockClient, cfg, logger)

	// Create request
	reqBody := map[string]interface{}{
		"user_id": "teen",
		"content": "learning content",
		"source":  "user_correction",
	}
	body, _ := json.Marshal(reqBody)

	req := httptest.NewRequest("POST", "/learn", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp clients.LearningResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.ID != "uuid-456" {
		t.Errorf("expected ID 'uuid-456', got %s", resp.ID)
	}
	if resp.Status != "processing" {
		t.Errorf("expected status 'processing', got %s", resp.Status)
	}
}

func TestLearnHandler_InvalidUserID(t *testing.T) {
	// Create config
	cfg := &config.Config{
		ValidUserIDs: []string{"dad", "mom", "teen", "child"},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewLearnHandler(nil, cfg, logger)

	// Create request with invalid user_id
	reqBody := map[string]interface{}{
		"user_id": "invalid",
		"content": "content",
		"source":  "test",
	}
	body, _ := json.Marshal(reqBody)

	req := httptest.NewRequest("POST", "/learn", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", w.Code)
	}
}

func TestLearnHandler_MissingFields(t *testing.T) {
	tests := []struct {
		name    string
		reqBody map[string]interface{}
	}{
		{
			name:    "missing user_id",
			reqBody: map[string]interface{}{"content": "test", "source": "test"},
		},
		{
			name:    "missing content",
			reqBody: map[string]interface{}{"user_id": "dad", "source": "test"},
		},
		{
			name:    "missing source",
			reqBody: map[string]interface{}{"user_id": "dad", "content": "test"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create config
			cfg := &config.Config{
				ValidUserIDs: []string{"dad", "mom", "teen", "child"},
			}

			// Create handler
			logger := slog.New(slog.NewTextHandler(io.Discard, nil))
			handler := NewLearnHandler(nil, cfg, logger)

			// Create request
			body, _ := json.Marshal(tt.reqBody)
			req := httptest.NewRequest("POST", "/learn", bytes.NewReader(body))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()

			// Execute handler
			handler.ServeHTTP(w, req)

			// Verify response
			if w.Code != http.StatusBadRequest {
				t.Errorf("expected status 400, got %d", w.Code)
			}
		})
	}
}

func TestLearnHandler_MethodNotAllowed(t *testing.T) {
	// Create config
	cfg := &config.Config{
		ValidUserIDs: []string{"dad", "mom", "teen", "child"},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewLearnHandler(nil, cfg, logger)

	// Create GET request (should be POST)
	req := httptest.NewRequest("GET", "/learn", nil)
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected status 405, got %d", w.Code)
	}
}
