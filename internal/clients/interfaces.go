package clients

import (
	"context"
	"time"
)

// LLMClientInterface defines the interface for LLM sidecar operations
type LLMClientInterface interface {
	Chat(ctx context.Context, req *ChatRequest) (*ChatResponse, error)
	Health(ctx context.Context) (time.Duration, error)
}

// VoiceClientInterface defines the interface for Voice sidecar operations
type VoiceClientInterface interface {
	ProcessVoice(ctx context.Context, wavData []byte) (*VoiceResponse, error)
	Health(ctx context.Context) (time.Duration, error)
}

// LearningClientInterface defines the interface for Learning sidecar operations
type LearningClientInterface interface {
	Submit(ctx context.Context, req *LearningRequest) (*LearningResponse, error)
	Health(ctx context.Context) (time.Duration, error)
}
