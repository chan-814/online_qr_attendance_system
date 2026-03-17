-- ==============================================================
--  QR ATTENDANCE PRO  –  Complete Database Setup
--  Database  : qr_attendance_pro   (SEPARATE from v1)
--  Compatible: MySQL 5.0+  (WAMP Server)
-- ==============================================================
--
--  HOW TO USE:
--  1. Open phpMyAdmin → http://localhost/phpmyadmin
--  2. Click the "SQL" tab at the top
--  3. Paste this ENTIRE file content
--  4. Click "Go"
--  Done! All 10 tables + sample data will be created.
--
-- ==============================================================

-- ── Step 1: Create the new separate database ─────────────────
CREATE DATABASE IF NOT EXISTS qr_attendance_pro
  DEFAULT CHARACTER SET utf8
  DEFAULT COLLATE utf8_general_ci;

USE qr_attendance_pro;

-- ==============================================================
-- TABLE 1 : admins
-- ==============================================================
CREATE TABLE IF NOT EXISTS admins (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(100) NOT NULL UNIQUE,
    password   VARCHAR(255) NOT NULL,
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ==============================================================
-- TABLE 2 : classes
-- ==============================================================
CREATE TABLE IF NOT EXISTS classes (
    id               INT          AUTO_INCREMENT PRIMARY KEY,
    class_name       VARCHAR(100) NOT NULL,
    department       VARCHAR(100) NOT NULL,
    teacher_id       INT          DEFAULT NULL,
    qr_count_offset  INT          DEFAULT 0,
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ==============================================================
-- TABLE 3 : teachers
-- ==============================================================
CREATE TABLE IF NOT EXISTS teachers (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    teacher_id VARCHAR(50)  NOT NULL UNIQUE,
    email      VARCHAR(100) NOT NULL UNIQUE,
    password   VARCHAR(255) NOT NULL,
    department VARCHAR(100) DEFAULT NULL,
    class_id   INT          DEFAULT NULL,
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- Add FK for classes.teacher_id now that teachers table exists
ALTER TABLE classes
  ADD CONSTRAINT fk_classes_teacher
  FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL;

-- ==============================================================
-- TABLE 4 : students
-- ==============================================================
CREATE TABLE IF NOT EXISTS students (
    id              INT          AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    register_number VARCHAR(50)  NOT NULL UNIQUE,
    email           VARCHAR(100) NOT NULL UNIQUE,
    password        VARCHAR(255) NOT NULL,
    class_id        INT          DEFAULT NULL,
    department      VARCHAR(100) DEFAULT NULL,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ==============================================================
-- TABLE 5 : qr_sessions
-- ==============================================================
CREATE TABLE IF NOT EXISTS qr_sessions (
    id              INT           AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(100)  NOT NULL UNIQUE,
    teacher_id      INT           NOT NULL,
    class_id        INT           NOT NULL,
    subject         VARCHAR(100)  NOT NULL,
    expires_at      DATETIME      NOT NULL,
    is_active       TINYINT(1)    DEFAULT 1,
    teacher_lat     DECIMAL(10,8) DEFAULT NULL,
    teacher_lng     DECIMAL(11,8) DEFAULT NULL,
    location_radius INT           DEFAULT 100,
    created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ==============================================================
-- TABLE 6 : attendance
-- ==============================================================
CREATE TABLE IF NOT EXISTS attendance (
    id         INT           AUTO_INCREMENT PRIMARY KEY,
    student_id INT           NOT NULL,
    session_id VARCHAR(100)  NOT NULL,
    class_id   INT           NOT NULL,
    subject    VARCHAR(100)  NOT NULL,
    status     VARCHAR(20)   DEFAULT 'Present',
    scan_lat   DECIMAL(10,8) DEFAULT NULL,
    scan_lng   DECIMAL(11,8) DEFAULT NULL,
    scanned_at TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_scan (student_id, session_id),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ==============================================================
-- TABLE 7 : password_resets   (Feature: Forgot Password)
-- ==============================================================
CREATE TABLE IF NOT EXISTS password_resets (
    id         INT         AUTO_INCREMENT PRIMARY KEY,
    email      VARCHAR(100) NOT NULL,
    otp        VARCHAR(6)   NOT NULL,
    user_type  VARCHAR(20)  NOT NULL,
    expires_at DATETIME     NOT NULL,
    is_used    TINYINT(1)   DEFAULT 0,
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ==============================================================
-- TABLE 8 : face_data   (Feature: Face Verification)
-- ==============================================================
CREATE TABLE IF NOT EXISTS face_data (
    id              INT  AUTO_INCREMENT PRIMARY KEY,
    student_id      INT  NOT NULL UNIQUE,
    face_descriptor TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ==============================================================
-- TABLE 9 : timetable   (Feature: Class Timetable)
-- ==============================================================
CREATE TABLE IF NOT EXISTS timetable (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    class_id   INT          NOT NULL,
    day_name   VARCHAR(20)  NOT NULL,
    period_no  INT          NOT NULL,
    subject    VARCHAR(100) NOT NULL,
    teacher_id INT          DEFAULT NULL,
    start_time VARCHAR(10)  NOT NULL,
    end_time   VARCHAR(10)  NOT NULL,
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ==============================================================
-- TABLE 10 : notifications   (Feature: Student Notifications)
-- ==============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    student_id INT          NOT NULL,
    title      VARCHAR(100) NOT NULL,
    message    TEXT         NOT NULL,
    is_read    TINYINT(1)   DEFAULT 0,
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


-- ==============================================================
--  DEFAULT LOGIN ACCOUNTS
-- ==============================================================

-- Admin  →  Email: admin@qrpro.com  |  Password: admin123
INSERT INTO admins (name, email, password) VALUES
('System Administrator', 'admin@qrpro.com',
 '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9');

-- Sample Classes
INSERT INTO classes (class_name, department) VALUES
('CS-A 2024',  'Computer Science'),
('CS-B 2024',  'Computer Science'),
('IT-A 2024',  'Information Technology'),
('ECE-A 2024', 'Electronics');

-- Teacher  →  Email: teacher@qrpro.com  |  Password: teacher123
INSERT INTO teachers (name, teacher_id, email, password, department, class_id) VALUES
('Dr. Ramesh Kumar', 'TCH001', 'teacher@qrpro.com',
 'cde383eee8ee7a4400adf7a15f716f179a2eb97646b37e089eb8d6d04e663416',
 'Computer Science', 1);

-- Student  →  Email: student@qrpro.com  |  Password: student123
INSERT INTO students (name, register_number, email, password, class_id, department) VALUES
('Arjun Sharma', 'REG2024001', 'student@qrpro.com',
 '703b0a3d6ad75b649a28adde7d83c6251da457549263bc7ff45ec709b0a8448b',
 1, 'Computer Science');

-- Sample Timetable for CS-A 2024 (class_id = 1)
INSERT INTO timetable (class_id, day_name, period_no, subject, teacher_id, start_time, end_time) VALUES
(1, 'Monday',    1, 'Data Structures',        1, '08:00', '09:00'),
(1, 'Monday',    2, 'Operating Systems',      1, '09:00', '10:00'),
(1, 'Monday',    3, 'Database Management',    1, '10:00', '11:00'),
(1, 'Tuesday',   1, 'Computer Networks',      1, '08:00', '09:00'),
(1, 'Tuesday',   2, 'Data Structures',        1, '09:00', '10:00'),
(1, 'Wednesday', 1, 'Operating Systems',      1, '08:00', '09:00'),
(1, 'Wednesday', 2, 'Database Management',    1, '09:00', '10:00'),
(1, 'Thursday',  1, 'Computer Networks',      1, '08:00', '09:00'),
(1, 'Thursday',  2, 'Data Structures Lab',    1, '09:00', '11:00'),
(1, 'Friday',    1, 'Database Management',    1, '08:00', '09:00'),
(1, 'Friday',    2, 'Operating Systems Lab',  1, '09:00', '11:00');

-- ==============================================================
--  Confirm all tables created successfully
-- ==============================================================
SHOW TABLES;
