package main

import (
	"crypto/rand"
	"encoding/hex"
	"sync"
	"time"
)

// Message represents a single conversation message
type Message struct {
	Role      string    `json:"role"`      // "user" or "assistant"
	Content   string    `json:"content"`   // The message content
	UserID    string    `json:"user_id"`   // Identified user (dad, mom, etc.)
	ModelUsed string    `json:"model_used,omitempty"` // Model used for response
	Timestamp time.Time `json:"timestamp"` // When the message was created
}

// Session represents a user session with conversation history
type Session struct {
	ID      string
	History []Message
	Created time.Time
	LastAccess time.Time
}

// SessionManager manages user sessions and conversation history
type SessionManager struct {
	sessions   map[string]*Session
	mu         sync.RWMutex
	maxHistory int
}

// NewSessionManager creates a new session manager
func NewSessionManager(maxHistory int) *SessionManager {
	return &SessionManager{
		sessions:   make(map[string]*Session),
		maxHistory: maxHistory,
	}
}

// GetOrCreateSession retrieves an existing session or creates a new one
func (sm *SessionManager) GetOrCreateSession(sessionID string) *Session {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	if sessionID == "" {
		sessionID = generateSessionID()
	}

	session, exists := sm.sessions[sessionID]
	if !exists {
		session = &Session{
			ID:         sessionID,
			History:    make([]Message, 0),
			Created:    time.Now(),
			LastAccess: time.Now(),
		}
		sm.sessions[sessionID] = session
	} else {
		session.LastAccess = time.Now()
	}

	return session
}

// AddMessage adds a message to the session history
func (sm *SessionManager) AddMessage(sessionID string, msg Message) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	session, exists := sm.sessions[sessionID]
	if !exists {
		return
	}

	msg.Timestamp = time.Now()
	session.History = append(session.History, msg)

	// Maintain max history size (FIFO)
	if len(session.History) > sm.maxHistory {
		session.History = session.History[len(session.History)-sm.maxHistory:]
	}

	session.LastAccess = time.Now()
}

// GetHistory returns the conversation history for a session
func (sm *SessionManager) GetHistory(sessionID string) []Message {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	session, exists := sm.sessions[sessionID]
	if !exists {
		return []Message{}
	}

	// Return a copy to prevent external modifications
	history := make([]Message, len(session.History))
	copy(history, session.History)
	return history
}

// ClearHistory clears the conversation history for a session
func (sm *SessionManager) ClearHistory(sessionID string) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	session, exists := sm.sessions[sessionID]
	if exists {
		session.History = make([]Message, 0)
		session.LastAccess = time.Now()
	}
}

// CleanupOldSessions removes sessions that haven't been accessed recently
func (sm *SessionManager) CleanupOldSessions(maxAge time.Duration) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	now := time.Now()
	for id, session := range sm.sessions {
		if now.Sub(session.LastAccess) > maxAge {
			delete(sm.sessions, id)
		}
	}
}

// generateSessionID creates a random session ID
func generateSessionID() string {
	bytes := make([]byte, 16)
	if _, err := rand.Read(bytes); err != nil {
		// Fallback to timestamp-based ID if random fails
		return hex.EncodeToString([]byte(time.Now().String()))
	}
	return hex.EncodeToString(bytes)
}
