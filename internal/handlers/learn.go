package handlers

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"github.com/assistant/orchestrator/internal/clients"
	"github.com/assistant/orchestrator/internal/config"
)

// LearnHandler handles POST /learn requests
type LearnHandler struct {
	learningClient clients.LearningClientInterface
	config         *config.Config
	logger         *slog.Logger
}

// NewLearnHandler creates a new learn handler
func NewLearnHandler(learningClient clients.LearningClientInterface, cfg *config.Config, logger *slog.Logger) *LearnHandler {
	return &LearnHandler{
		learningClient: learningClient,
		config:         cfg,
		logger:         logger,
	}
}

// learnRequest represents the incoming request structure
type learnRequest struct {
	UserID  string `json:"user_id"`
	Content string `json:"content"`
	Source  string `json:"source"`
}

// ServeHTTP implements http.Handler
func (h *LearnHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Only accept POST
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed", "")
		return
	}

	// Parse request body
	var req learnRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.logger.Warn("failed to parse learn request", "error", err)
		writeError(w, http.StatusBadRequest, "invalid request body", err.Error())
		return
	}

	// Validate user_id
	if req.UserID == "" {
		writeError(w, http.StatusBadRequest, "user_id is required", "")
		return
	}

	if !h.config.IsValidUserID(req.UserID) {
		h.logger.Warn("invalid user_id", "user_id", req.UserID)
		writeError(w, http.StatusBadRequest, "invalid user_id", "user_id must be one of: dad, mom, teen, child")
		return
	}

	// Validate content
	if req.Content == "" {
		writeError(w, http.StatusBadRequest, "content is required", "")
		return
	}

	// Validate source
	if req.Source == "" {
		writeError(w, http.StatusBadRequest, "source is required", "")
		return
	}

	h.logger.Info("processing learn request", "user_id", req.UserID, "source", req.Source)

	// Call Learning sidecar
	learningReq := &clients.LearningRequest{
		UserID:  req.UserID,
		Content: req.Content,
		Source:  req.Source,
	}

	learningResp, err := h.learningClient.Submit(r.Context(), learningReq)
	if err != nil {
		h.logger.Error("Learning sidecar request failed", "error", err)
		writeError(w, http.StatusServiceUnavailable, "learning sidecar unavailable", err.Error())
		return
	}

	// Return Learning response
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(learningResp)
}
