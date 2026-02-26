package clients

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestLearningClient_Submit_Success(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify request
		if r.Method != "POST" {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/learning/submit" {
			t.Errorf("expected /learning/submit, got %s", r.URL.Path)
		}

		// Parse request
		var req LearningRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatalf("failed to decode request: %v", err)
		}

		// Verify request content
		if req.UserID != "teen" {
			t.Errorf("expected user_id 'teen', got %s", req.UserID)
		}
		if req.Content != "test content" {
			t.Errorf("expected content 'test content', got %s", req.Content)
		}
		if req.Source != "user_correction" {
			t.Errorf("expected source 'user_correction', got %s", req.Source)
		}

		// Send response
		resp := LearningResponse{
			ID:     "uuid-123",
			Status: "processing",
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	// Create client
	client := NewLearningClient(server.URL, 5*time.Second)

	// Make request
	req := &LearningRequest{
		UserID:  "teen",
		Content: "test content",
		Source:  "user_correction",
	}

	resp, err := client.Submit(context.Background(), req)
	if err != nil {
		t.Fatalf("Submit failed: %v", err)
	}

	// Verify response
	if resp.ID != "uuid-123" {
		t.Errorf("expected ID 'uuid-123', got %s", resp.ID)
	}
	if resp.Status != "processing" {
		t.Errorf("expected status 'processing', got %s", resp.Status)
	}
}

func TestLearningClient_Submit_ServerError(t *testing.T) {
	// Create mock server that returns error
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("internal error"))
	}))
	defer server.Close()

	// Create client
	client := NewLearningClient(server.URL, 5*time.Second)

	// Make request
	req := &LearningRequest{
		UserID:  "child",
		Content: "test",
		Source:  "test",
	}

	_, err := client.Submit(context.Background(), req)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestLearningClient_Health_Success(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/health" {
			t.Errorf("expected /health, got %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	// Create client
	client := NewLearningClient(server.URL, 5*time.Second)

	// Check health
	latency, err := client.Health(context.Background())
	if err != nil {
		t.Fatalf("Health check failed: %v", err)
	}

	if latency <= 0 {
		t.Error("expected positive latency")
	}
}

func TestLearningClient_Health_Failure(t *testing.T) {
	// Create mock server that returns error
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer server.Close()

	// Create client
	client := NewLearningClient(server.URL, 5*time.Second)

	// Check health
	_, err := client.Health(context.Background())
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}
