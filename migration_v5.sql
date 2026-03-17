-- ============================================================
--  QR ATTENDANCE PRO – Migration Script v5
--  Run this if you already have an existing database and
--  want to upgrade to v5 without losing data.
--
--  HOW TO USE:
--  phpMyAdmin → select "qr_attendance_pro" DB → SQL tab → paste → Go
-- ============================================================

USE qr_attendance_pro;

-- Add student scan location columns to attendance table
ALTER TABLE attendance
  ADD COLUMN IF NOT EXISTS scan_lat DECIMAL(10,8) DEFAULT NULL AFTER status,
  ADD COLUMN IF NOT EXISTS scan_lng DECIMAL(11,8) DEFAULT NULL AFTER scan_lat;

-- Add qr_count_offset to classes (if upgrading from v2 or earlier)
ALTER TABLE classes
  ADD COLUMN IF NOT EXISTS qr_count_offset INT DEFAULT 0;

-- Add location lock columns to qr_sessions (if upgrading from v1)
ALTER TABLE qr_sessions
  ADD COLUMN IF NOT EXISTS teacher_lat     DECIMAL(10,8) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS teacher_lng     DECIMAL(11,8) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS location_radius INT           DEFAULT 100;

SELECT 'Migration v5 complete!' AS status;
