package clients

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestVoiceClient_ProcessVoice_Identified(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify request
		if r.Method != "POST" {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/voice/process" {
			t.Errorf("expected /voice/process, got %s", r.URL.Path)
		}

		// Parse multipart form
		if err := r.ParseMultipartForm(32 << 20); err != nil {
			t.Fatalf("failed to parse multipart form: %v", err)
		}

		// Verify file exists
		_, _, err := r.FormFile("file")
		if err != nil {
			t.Fatalf("expected file in form: %v", err)
		}

		// Send response
		resp := VoiceResponse{
			Status:     "identified",
			UserID:     "mom",
			Confidence: 0.92,
			Transcript: "test transcript",
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	// Create client
	client := NewVoiceClient(server.URL, 5*time.Second)

	// Make request
	wavData := []byte("fake wav data")
	resp, err := client.ProcessVoice(context.Background(), wavData)
	if err != nil {
		t.Fatalf("ProcessVoice failed: %v", err)
	}

	// Verify response
	if resp.Status != "identified" {
		t.Errorf("expected status 'identified', got %s", resp.Status)
	}
	if resp.UserID != "mom" {
		t.Errorf("expected user_id 'mom', got %s", resp.UserID)
	}
	if resp.Confidence != 0.92 {
		t.Errorf("expected confidence 0.92, got %f", resp.Confidence)
	}
	if resp.Transcript != "test transcript" {
		t.Errorf("expected transcript 'test transcript', got %s", resp.Transcript)
	}
}

func TestVoiceClient_ProcessVoice_NoSpeech(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := VoiceResponse{
			Status: "no_speech",
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	// Create client
	client := NewVoiceClient(server.URL, 5*time.Second)

	// Make request
	resp, err := client.ProcessVoice(context.Background(), []byte("fake wav"))
	if err != nil {
		t.Fatalf("ProcessVoice failed: %v", err)
	}

	if resp.Status != "no_speech" {
		t.Errorf("expected status 'no_speech', got %s", resp.Status)
	}
}

func TestVoiceClient_ProcessVoice_Rejected(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := VoiceResponse{
			Status:     "rejected",
			Confidence: 0.35,
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	// Create client
	client := NewVoiceClient(server.URL, 5*time.Second)

	// Make request
	resp, err := client.ProcessVoice(context.Background(), []byte("fake wav"))
	if err != nil {
		t.Fatalf("ProcessVoice failed: %v", err)
	}

	if resp.Status != "rejected" {
		t.Errorf("expected status 'rejected', got %s", resp.Status)
	}
	if resp.Confidence != 0.35 {
		t.Errorf("expected confidence 0.35, got %f", resp.Confidence)
	}
}

func TestVoiceClient_ProcessVoice_Fallback(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := VoiceResponse{
			Status:     "fallback",
			UserID:     "dad",
			Confidence: 0.0,
			Transcript: "fallback transcript",
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	// Create client
	client := NewVoiceClient(server.URL, 5*time.Second)

	// Make request
	resp, err := client.ProcessVoice(context.Background(), []byte("fake wav"))
	if err != nil {
		t.Fatalf("ProcessVoice failed: %v", err)
	}

	if resp.Status != "fallback" {
		t.Errorf("expected status 'fallback', got %s", resp.Status)
	}
	if resp.UserID != "dad" {
		t.Errorf("expected user_id 'dad', got %s", resp.UserID)
	}
}

func TestVoiceClient_Health_Success(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/health" {
			t.Errorf("expected /health, got %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	// Create client
	client := NewVoiceClient(server.URL, 5*time.Second)

	// Check health
	latency, err := client.Health(context.Background())
	if err != nil {
		t.Fatalf("Health check failed: %v", err)
	}

	if latency <= 0 {
		t.Error("expected positive latency")
	}
}
