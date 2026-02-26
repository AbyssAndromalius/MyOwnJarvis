package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"log/slog"
	"io"

	"github.com/assistant/orchestrator/internal/clients"
	"github.com/assistant/orchestrator/internal/config"
)

// mockLLMClient implements a mock LLM client for testing
type mockLLMClient struct {
	chatFunc   func(ctx context.Context, req *clients.ChatRequest) (*clients.ChatResponse, error)
	healthFunc func(ctx context.Context) (time.Duration, error)
}

func (m *mockLLMClient) Chat(ctx context.Context, req *clients.ChatRequest) (*clients.ChatResponse, error) {
	if m.chatFunc != nil {
		return m.chatFunc(ctx, req)
	}
	return nil, nil
}

func (m *mockLLMClient) Health(ctx context.Context) (time.Duration, error) {
	if m.healthFunc != nil {
		return m.healthFunc(ctx)
	}
	return 0, nil
}

func TestChatHandler_ValidRequest(t *testing.T) {
	// Create config
	cfg := &config.Config{
		ValidUserIDs: []string{"dad", "mom", "teen", "child"},
	}

	// Create mock LLM client
	mockClient := &mockLLMClient{
		chatFunc: func(ctx context.Context, req *clients.ChatRequest) (*clients.ChatResponse, error) {
			return &clients.ChatResponse{
				Response:     "test response",
				ModelUsed:    "llama3.1:8b",
				MemoriesUsed: []string{},
				UserID:       req.UserID,
			}, nil
		},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewChatHandler(mockClient, cfg, logger)

	// Create request
	reqBody := map[string]interface{}{
		"user_id":              "dad",
		"message":              "test message",
		"conversation_history": []string{},
	}
	body, _ := json.Marshal(reqBody)

	req := httptest.NewRequest("POST", "/chat", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp clients.ChatResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Response != "test response" {
		t.Errorf("expected response 'test response', got %s", resp.Response)
	}
	if resp.UserID != "dad" {
		t.Errorf("expected user_id 'dad', got %s", resp.UserID)
	}
}

func TestChatHandler_InvalidUserID(t *testing.T) {
	// Create config
	cfg := &config.Config{
		ValidUserIDs: []string{"dad", "mom", "teen", "child"},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewChatHandler(nil, cfg, logger)

	// Create request with invalid user_id
	reqBody := map[string]interface{}{
		"user_id": "invalid",
		"message": "test",
	}
	body, _ := json.Marshal(reqBody)

	req := httptest.NewRequest("POST", "/chat", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", w.Code)
	}

	var errResp map[string]string
	if err := json.NewDecoder(w.Body).Decode(&errResp); err != nil {
		t.Fatalf("failed to decode error response: %v", err)
	}

	if errResp["error"] != "invalid user_id" {
		t.Errorf("expected error 'invalid user_id', got %s", errResp["error"])
	}
}

func TestChatHandler_MissingUserID(t *testing.T) {
	// Create config
	cfg := &config.Config{
		ValidUserIDs: []string{"dad", "mom", "teen", "child"},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewChatHandler(nil, cfg, logger)

	// Create request without user_id
	reqBody := map[string]interface{}{
		"message": "test",
	}
	body, _ := json.Marshal(reqBody)

	req := httptest.NewRequest("POST", "/chat", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", w.Code)
	}
}

func TestChatHandler_MissingMessage(t *testing.T) {
	// Create config
	cfg := &config.Config{
		ValidUserIDs: []string{"dad", "mom", "teen", "child"},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewChatHandler(nil, cfg, logger)

	// Create request without message
	reqBody := map[string]interface{}{
		"user_id": "dad",
	}
	body, _ := json.Marshal(reqBody)

	req := httptest.NewRequest("POST", "/chat", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", w.Code)
	}
}

func TestChatHandler_MethodNotAllowed(t *testing.T) {
	// Create config
	cfg := &config.Config{
		ValidUserIDs: []string{"dad", "mom", "teen", "child"},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewChatHandler(nil, cfg, logger)

	// Create GET request (should be POST)
	req := httptest.NewRequest("GET", "/chat", nil)
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected status 405, got %d", w.Code)
	}
}
