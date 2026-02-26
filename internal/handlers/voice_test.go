package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/assistant/orchestrator/internal/clients"
)

// mockVoiceClient implements a mock Voice client for testing
type mockVoiceClient struct {
	processFunc func(ctx context.Context, wavData []byte) (*clients.VoiceResponse, error)
	healthFunc  func(ctx context.Context) (time.Duration, error)
}

func (m *mockVoiceClient) ProcessVoice(ctx context.Context, wavData []byte) (*clients.VoiceResponse, error) {
	if m.processFunc != nil {
		return m.processFunc(ctx, wavData)
	}
	return nil, nil
}

func (m *mockVoiceClient) Health(ctx context.Context) (time.Duration, error) {
	if m.healthFunc != nil {
		return m.healthFunc(ctx)
	}
	return 0, nil
}

func createMultipartRequest(t *testing.T, wavData []byte) *http.Request {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)
	
	part, err := writer.CreateFormFile("file", "test.wav")
	if err != nil {
		t.Fatalf("failed to create form file: %v", err)
	}
	
	if _, err := part.Write(wavData); err != nil {
		t.Fatalf("failed to write wav data: %v", err)
	}
	
	if err := writer.Close(); err != nil {
		t.Fatalf("failed to close writer: %v", err)
	}
	
	req := httptest.NewRequest("POST", "/voice", &buf)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	
	return req
}

func TestVoiceHandler_Identified(t *testing.T) {
	// Create mock clients
	mockVoice := &mockVoiceClient{
		processFunc: func(ctx context.Context, wavData []byte) (*clients.VoiceResponse, error) {
			return &clients.VoiceResponse{
				Status:     "identified",
				UserID:     "mom",
				Confidence: 0.89,
				Transcript: "test transcript",
			}, nil
		},
	}

	mockLLM := &mockLLMClient{
		chatFunc: func(ctx context.Context, req *clients.ChatRequest) (*clients.ChatResponse, error) {
			return &clients.ChatResponse{
				Response:  "llm response",
				ModelUsed: "llama3.1:8b",
				UserID:    req.UserID,
			}, nil
		},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewVoiceHandler(mockVoice, mockLLM, logger)

	// Create request
	req := createMultipartRequest(t, []byte("fake wav data"))
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp voiceSuccessResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Status != "identified" {
		t.Errorf("expected status 'identified', got %s", resp.Status)
	}
	if resp.UserID != "mom" {
		t.Errorf("expected user_id 'mom', got %s", resp.UserID)
	}
	if resp.Confidence != 0.89 {
		t.Errorf("expected confidence 0.89, got %f", resp.Confidence)
	}
	if resp.Response != "llm response" {
		t.Errorf("expected response 'llm response', got %s", resp.Response)
	}
	if resp.Fallback != false {
		t.Errorf("expected fallback false, got %v", resp.Fallback)
	}
}

func TestVoiceHandler_Fallback(t *testing.T) {
	// Create mock clients
	mockVoice := &mockVoiceClient{
		processFunc: func(ctx context.Context, wavData []byte) (*clients.VoiceResponse, error) {
			return &clients.VoiceResponse{
				Status:     "fallback",
				UserID:     "dad",
				Confidence: 0.0,
				Transcript: "fallback transcript",
			}, nil
		},
	}

	mockLLM := &mockLLMClient{
		chatFunc: func(ctx context.Context, req *clients.ChatRequest) (*clients.ChatResponse, error) {
			return &clients.ChatResponse{
				Response:  "fallback llm response",
				ModelUsed: "llama3.1:8b",
				UserID:    req.UserID,
			}, nil
		},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewVoiceHandler(mockVoice, mockLLM, logger)

	// Create request
	req := createMultipartRequest(t, []byte("fake wav data"))
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp voiceSuccessResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Status != "fallback" {
		t.Errorf("expected status 'fallback', got %s", resp.Status)
	}
	if resp.Fallback != true {
		t.Errorf("expected fallback true, got %v", resp.Fallback)
	}
}

func TestVoiceHandler_NoSpeech(t *testing.T) {
	// Create mock client
	mockVoice := &mockVoiceClient{
		processFunc: func(ctx context.Context, wavData []byte) (*clients.VoiceResponse, error) {
			return &clients.VoiceResponse{
				Status: "no_speech",
			}, nil
		},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewVoiceHandler(mockVoice, nil, logger)

	// Create request
	req := createMultipartRequest(t, []byte("fake wav data"))
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]string
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp["status"] != "no_speech" {
		t.Errorf("expected status 'no_speech', got %s", resp["status"])
	}
}

func TestVoiceHandler_Rejected(t *testing.T) {
	// Create mock client
	mockVoice := &mockVoiceClient{
		processFunc: func(ctx context.Context, wavData []byte) (*clients.VoiceResponse, error) {
			return &clients.VoiceResponse{
				Status:     "rejected",
				Confidence: 0.41,
			}, nil
		},
	}

	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewVoiceHandler(mockVoice, nil, logger)

	// Create request
	req := createMultipartRequest(t, []byte("fake wav data"))
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp["status"] != "rejected" {
		t.Errorf("expected status 'rejected', got %s", resp["status"])
	}
	if resp["confidence"] != 0.41 {
		t.Errorf("expected confidence 0.41, got %v", resp["confidence"])
	}
}

func TestVoiceHandler_MethodNotAllowed(t *testing.T) {
	// Create handler
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	handler := NewVoiceHandler(nil, nil, logger)

	// Create GET request (should be POST)
	req := httptest.NewRequest("GET", "/voice", nil)
	w := httptest.NewRecorder()

	// Execute handler
	handler.ServeHTTP(w, req)

	// Verify response
	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected status 405, got %d", w.Code)
	}
}
