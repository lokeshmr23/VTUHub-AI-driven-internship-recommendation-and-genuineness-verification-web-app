-- =====================================================================
-- InternMatch AI — MySQL schema (utf8mb4 / InnoDB)
-- Usage:
--   mysql -u root -p -e "CREATE DATABASE internmatch CHARACTER SET utf8mb4;"
--   mysql -u root -p internmatch < sql/schema_mysql.sql
--   mysql -u root -p internmatch < sql/seed_data.sql      -- demo rows (exported)
-- =====================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS trust_audit_log;
DROP TABLE IF EXISTS feedback;
DROP TABLE IF EXISTS applications;
DROP TABLE IF EXISTS internships;
DROP TABLE IF EXISTS domain_intel;
DROP TABLE IF EXISTS resume_uploads;
DROP TABLE IF EXISTS student_profiles;
DROP TABLE IF EXISTS users;

-- ---------------------------------------------------------------- users
CREATE TABLE users (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  name           VARCHAR(120)  NOT NULL,
  email          VARCHAR(190)  NOT NULL,
  password_hash  VARCHAR(255)  NOT NULL,
  role           VARCHAR(20)   NOT NULL DEFAULT 'student',
  phone          VARCHAR(20)   NULL,
  is_active      TINYINT(1)    NOT NULL DEFAULT 1,
  created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login     DATETIME      NULL,
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------ student_profiles
CREATE TABLE student_profiles (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  user_id            INT           NOT NULL,
  roll_number        VARCHAR(40)   NULL,
  college            VARCHAR(190)  NULL,
  branch             VARCHAR(90)   NULL,
  graduation_year    INT           NULL,
  cgpa               FLOAT         NULL,
  preferred_domain   VARCHAR(60)   NULL,
  preferred_location VARCHAR(90)   NULL,
  work_mode_pref     VARCHAR(20)   DEFAULT 'any',
  phone              VARCHAR(20)   NULL,
  resume_filename    VARCHAR(255)  NULL,
  resume_text        LONGTEXT      NULL,
  resume_uploaded_at DATETIME      NULL,
  skills             JSON          NULL,
  skill_details      JSON          NULL,
  skill_vector       JSON          NULL,
  parsed_meta        JSON          NULL,
  ats_score          INT           DEFAULT 0,
  updated_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_profile_user (user_id),
  KEY idx_profile_roll (roll_number),
  KEY idx_profile_domain (preferred_domain),
  CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------- resume_uploads
CREATE TABLE resume_uploads (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  student_id    INT          NOT NULL,
  filename      VARCHAR(255) NULL,
  file_type     VARCHAR(10)  NULL,
  size_bytes    INT          DEFAULT 0,
  skills_found  INT          DEFAULT 0,
  ats_score     INT          DEFAULT 0,
  text_chars    INT          DEFAULT 0,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_resume_student (student_id),
  CONSTRAINT fk_resume_student FOREIGN KEY (student_id)
    REFERENCES student_profiles (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------- domain_intel
CREATE TABLE domain_intel (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  domain           VARCHAR(190) NOT NULL,
  age_days         INT          DEFAULT 0,
  is_free_provider TINYINT(1)   DEFAULT 0,
  is_disposable    TINYINT(1)   DEFAULT 0,
  is_blacklisted   TINYINT(1)   DEFAULT 0,
  mx_valid         TINYINT(1)   DEFAULT 1,
  source           VARCHAR(40)  DEFAULT 'heuristic',
  last_checked     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_domain (domain),
  KEY idx_domain_blacklist (is_blacklisted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------ internships
CREATE TABLE internships (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  title              VARCHAR(190) NOT NULL,
  company            VARCHAR(190) NOT NULL,
  company_domain     VARCHAR(190) NULL,
  contact_email      VARCHAR(190) NULL,
  location           VARCHAR(120) NULL,
  work_mode          VARCHAR(20)  DEFAULT 'onsite',
  domain             VARCHAR(60)  NULL,
  description        LONGTEXT     NULL,
  skills_required    JSON         NULL,
  stipend            INT          DEFAULT 0,
  duration_months    INT          DEFAULT 3,
  openings           INT          DEFAULT 1,
  apply_url          VARCHAR(400) NULL,
  posted_date        DATE         NULL,
  deadline           DATE         NULL,
  source             VARCHAR(40)  DEFAULT 'partner',
  -- trust engine outputs
  trust_score        INT          DEFAULT 0,
  rule_score         FLOAT        DEFAULT 0,
  ml_fraud_prob      FLOAT        DEFAULT 0,
  fraud_flag         TINYINT(1)   DEFAULT 0,
  badge              VARCHAR(10)  DEFAULT 'Amber',
  hard_check_failed  TINYINT(1)   DEFAULT 0,
  trust_breakdown    JSON         NULL,
  red_flags          JSON         NULL,
  override_by_admin  TINYINT(1)   DEFAULT 0,
  override_note      VARCHAR(400) NULL,
  trust_checked_at   DATETIME     NULL,
  created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_intern_company (company),
  KEY idx_intern_domain_field (domain),
  KEY idx_intern_trust (trust_score),
  KEY idx_intern_flag (fraud_flag),
  KEY idx_intern_location (location),
  KEY idx_intern_posted (posted_date),
  KEY idx_intern_company_domain (company_domain),
  FULLTEXT KEY ft_intern_search (title, company, description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------- applications
CREATE TABLE applications (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  student_id    INT          NOT NULL,
  internship_id INT          NOT NULL,
  status        VARCHAR(24)  DEFAULT 'applied',
  match_score   FLOAT        DEFAULT 0,
  notes         VARCHAR(400) NULL,
  applied_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_student_listing (student_id, internship_id),
  KEY idx_app_status (status),
  CONSTRAINT fk_app_student FOREIGN KEY (student_id)
    REFERENCES student_profiles (id) ON DELETE CASCADE,
  CONSTRAINT fk_app_internship FOREIGN KEY (internship_id)
    REFERENCES internships (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------- feedback
CREATE TABLE feedback (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  student_id    INT          NOT NULL,
  internship_id INT          NOT NULL,
  rating        INT          NOT NULL,
  verdict       VARCHAR(20)  NOT NULL,
  comment       VARCHAR(500) NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_feedback_internship (internship_id),
  KEY idx_feedback_student (student_id),
  KEY idx_feedback_verdict (verdict),
  CONSTRAINT fk_feedback_student FOREIGN KEY (student_id)
    REFERENCES student_profiles (id) ON DELETE CASCADE,
  CONSTRAINT fk_feedback_internship FOREIGN KEY (internship_id)
    REFERENCES internships (id) ON DELETE CASCADE,
  CONSTRAINT chk_feedback_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------- trust_audit_log
CREATE TABLE trust_audit_log (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  internship_id INT          NULL,
  actor         VARCHAR(120) DEFAULT 'system',
  action        VARCHAR(60)  NULL,
  old_score     INT          NULL,
  new_score     INT          NULL,
  old_badge     VARCHAR(10)  NULL,
  new_badge     VARCHAR(10)  NULL,
  note          VARCHAR(400) NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_audit_internship (internship_id),
  KEY idx_audit_action (action),
  CONSTRAINT fk_audit_internship FOREIGN KEY (internship_id)
    REFERENCES internships (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
