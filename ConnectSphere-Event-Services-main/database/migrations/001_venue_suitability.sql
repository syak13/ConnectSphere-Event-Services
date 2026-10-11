-- =====================================================================
-- Migration 001 — Venue Suitability Check
-- For a database created from this branch's schema.sql BEFORE the Venue
-- Suitability Check was added. A fresh import of the updated schema.sql
-- already includes these.
-- (venue_layouts and venue_accessibility_features belong to the Venue
--  Catalogue and are already in schema.sql.)
-- =====================================================================
USE connectsphere;

ALTER TABLE events
    ADD COLUMN accessibility_requirements JSON NULL AFTER accessibility_needs;

CREATE TABLE IF NOT EXISTS venue_suitability_overrides (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_id        BIGINT UNSIGNED NOT NULL,
    venue_id        BIGINT UNSIGNED NOT NULL,
    flag_type       ENUM('capacity','accessibility','layout') NOT NULL,
    reason          TEXT NOT NULL,
    basis           JSON NOT NULL,
    overridden_by   BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cleared_at      DATETIME NULL,
    cleared_reason  VARCHAR(255) NULL,
    CONSTRAINT fk_vso_event FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    CONSTRAINT fk_vso_venue FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE CASCADE,
    CONSTRAINT fk_vso_user FOREIGN KEY (overridden_by) REFERENCES users(id),
    INDEX idx_vso_event_venue (event_id, venue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
