package clients

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestLLMClient_Chat_Success(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify request
		if r.Method != "POST" {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/chat" {
			t.Errorf("expected /chat, got %s", r.URL.Path)
		}

		// Parse request
		var req ChatRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatalf("failed to decode request: %v", err)
		}

		// Verify request content
		if req.UserID != "dad" {
			t.Errorf("expected user_id 'dad', got %s", req.UserID)
		}
		if req.Message != "test message" {
			t.Errorf("expected message 'test message', got %s", req.Message)
		}

		// Send response
		resp := ChatResponse{
			Response:     "test response",
			ModelUsed:    "llama3.1:8b",
			MemoriesUsed: []string{"memory1"},
			UserID:       "dad",
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	// Create client
	client := NewLLMClient(server.URL, 5*time.Second)

	// Make request
	req := &ChatRequest{
		UserID:              "dad",
		Message:             "test message",
		ConversationHistory: []string{},
	}

	resp, err := client.Chat(context.Background(), req)
	if err != nil {
		t.Fatalf("Chat failed: %v", err)
	}

	// Verify response
	if resp.Response != "test response" {
		t.Errorf("expected response 'test response', got %s", resp.Response)
	}
	if resp.ModelUsed != "llama3.1:8b" {
		t.Errorf("expected model 'llama3.1:8b', got %s", resp.ModelUsed)
	}
	if resp.UserID != "dad" {
		t.Errorf("expected user_id 'dad', got %s", resp.UserID)
	}
}

func TestLLMClient_Chat_ServerError(t *testing.T) {
	// Create mock server that returns error
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("internal error"))
	}))
	defer server.Close()

	// Create client
	client := NewLLMClient(server.URL, 5*time.Second)

	// Make request
	req := &ChatRequest{
		UserID:  "dad",
		Message: "test",
	}

	_, err := client.Chat(context.Background(), req)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestLLMClient_Health_Success(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/health" {
			t.Errorf("expected /health, got %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	// Create client
	client := NewLLMClient(server.URL, 5*time.Second)

	// Check health
	latency, err := client.Health(context.Background())
	if err != nil {
		t.Fatalf("Health check failed: %v", err)
	}

	if latency <= 0 {
		t.Error("expected positive latency")
	}
}

func TestLLMClient_Health_Failure(t *testing.T) {
	// Create mock server that returns error
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer server.Close()

	// Create client
	client := NewLLMClient(server.URL, 5*time.Second)

	// Check health
	_, err := client.Health(context.Background())
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}
