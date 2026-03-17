-- ============================================================
--  QR ATTENDANCE PRO  –  Database Migration (for EXISTING DBs)
--  Run this ONLY if you already have the database from a
--  previous version. If you are setting up fresh, use
--  database_pro.sql instead — it already has all columns.
-- ============================================================

USE qr_attendance_pro;

-- 1. Add QR count reset support to classes table
ALTER TABLE classes
    ADD COLUMN IF NOT EXISTS qr_count_offset INT DEFAULT 0;

-- 2. Add location verification columns to qr_sessions table
ALTER TABLE qr_sessions
    ADD COLUMN IF NOT EXISTS teacher_lat     DECIMAL(10,8) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS teacher_lng     DECIMAL(11,8) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS location_radius INT           DEFAULT 100;

-- Confirm
SELECT 'Migration complete! All columns added successfully.' AS status;
SHOW COLUMNS FROM classes;
SHOW COLUMNS FROM qr_sessions;
