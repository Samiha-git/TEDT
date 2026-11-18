-- TEDT Education Data Foundation — SQLite schema (Lot 1)
-- Generated from tedt_core.foundation.initialize(); no data rows.

CREATE TABLE dataset (
            dataset_code TEXT PRIMARY KEY, dataset_name TEXT NOT NULL, family TEXT,
            expected_grain TEXT, security_classification TEXT NOT NULL DEFAULT 'PUBLIC',
            schema_version TEXT NOT NULL DEFAULT '1.0'
        );

CREATE TABLE dim_education_level (
            education_level_code TEXT PRIMARY KEY, label_fr TEXT NOT NULL, label_ar TEXT,
            level_order INTEGER, framework_version TEXT
        );

CREATE TABLE dim_geography (
            geography_id TEXT PRIMARY KEY, geography_level TEXT NOT NULL,
            canonical_code TEXT, name_fr TEXT NOT NULL, name_ar TEXT,
            parent_geography_id TEXT, nomenclature_code TEXT, nomenclature_version TEXT,
            valid_from TEXT, valid_to TEXT,
            FOREIGN KEY(parent_geography_id) REFERENCES dim_geography(geography_id)
        );

CREATE TABLE dim_milieu (
            milieu_code TEXT PRIMARY KEY, label_fr TEXT NOT NULL, label_ar TEXT, source_code TEXT
        );

CREATE TABLE dim_period (
            period_id TEXT PRIMARY KEY, period_type TEXT NOT NULL, period_label TEXT NOT NULL,
            start_date TEXT NOT NULL, end_date TEXT NOT NULL, calendar_system TEXT NOT NULL DEFAULT 'gregorian'
        );

CREATE TABLE dim_sex (
            sex_code TEXT PRIMARY KEY, label_fr TEXT NOT NULL, label_ar TEXT, source_code TEXT
        );

CREATE TABLE fact_enrolment (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT, tedt_institution_id TEXT,
            education_level_code TEXT, sex_code TEXT, enrolled_count REAL, eligible_population REAL,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(education_level_code) REFERENCES dim_education_level(education_level_code),
            FOREIGN KEY(sex_code) REFERENCES dim_sex(sex_code),
            FOREIGN KEY(source_id) REFERENCES source(source_id),
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE TABLE fact_expenditure (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT,
            programme_code TEXT, education_level_code TEXT, expenditure_nature TEXT,
            budget_amount REAL, executed_amount REAL, currency_code TEXT NOT NULL,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(education_level_code) REFERENCES dim_education_level(education_level_code),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE TABLE fact_infrastructure (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT, tedt_institution_id TEXT,
            asset_type TEXT NOT NULL, asset_count REAL, operational_count REAL, condition_code TEXT,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE TABLE fact_learning_outcome (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT, tedt_institution_id TEXT,
            education_level_code TEXT, subject_code TEXT, assessment_code TEXT,
            candidate_count REAL, successful_count REAL, mean_score REAL, published_rate REAL,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(education_level_code) REFERENCES dim_education_level(education_level_code),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE TABLE fact_observation (
            observation_id TEXT PRIMARY KEY, indicator_code TEXT NOT NULL,
            indicator_version TEXT NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
            geography_id TEXT, tedt_institution_id TEXT, dimension_json TEXT NOT NULL,
            value REAL, numerator REAL, denominator REAL, unit TEXT,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            loaded_at TEXT NOT NULL,
            FOREIGN KEY(indicator_code, indicator_version) REFERENCES indicator_dictionary(indicator_code, version),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(source_id) REFERENCES source(source_id),
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE TABLE fact_staff (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT, tedt_institution_id TEXT,
            education_level_code TEXT, discipline_code TEXT, staff_count REAL, vacancy_count REAL,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(education_level_code) REFERENCES dim_education_level(education_level_code),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE TABLE fact_territorial_indicator (
            fact_id TEXT PRIMARY KEY, period_id TEXT NOT NULL, geography_id TEXT NOT NULL,
            indicator_code TEXT NOT NULL, indicator_version TEXT NOT NULL, dimension_json TEXT NOT NULL,
            value REAL, numerator REAL, denominator REAL, unit TEXT,
            source_id TEXT NOT NULL, batch_id TEXT NOT NULL, quality_status TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES dim_period(period_id),
            FOREIGN KEY(geography_id) REFERENCES dim_geography(geography_id),
            FOREIGN KEY(indicator_code,indicator_version) REFERENCES indicator_dictionary(indicator_code,version),
            FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE TABLE indicator_dictionary (
            indicator_code TEXT NOT NULL, version TEXT NOT NULL, label_fr TEXT NOT NULL,
            label_ar TEXT, indicator_type TEXT NOT NULL, definition TEXT NOT NULL,
            analytical_purpose TEXT, formula TEXT, numerator TEXT, denominator TEXT,
            unit TEXT, grain TEXT, disaggregation TEXT, periodicity TEXT,
            reference_period TEXT, source_owner TEXT, reliability_status TEXT,
            methodological_limits TEXT, missing_value_rule TEXT, status TEXT NOT NULL,
            PRIMARY KEY(indicator_code, version)
        );

CREATE TABLE ingestion_batch (
            batch_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, dataset_code TEXT NOT NULL,
            source_owner TEXT NOT NULL, source_title TEXT NOT NULL, source_reference TEXT NOT NULL,
            received_at TEXT NOT NULL, received_by TEXT NOT NULL,
            reference_period_start TEXT NOT NULL, reference_period_end TEXT NOT NULL,
            geographic_level TEXT NOT NULL, granularity TEXT NOT NULL,
            declared_license_or_authorization TEXT NOT NULL,
            security_classification TEXT NOT NULL, language TEXT NOT NULL,
            source_filename TEXT NOT NULL, stored_filename TEXT NOT NULL,
            sha256 TEXT NOT NULL, file_size INTEGER NOT NULL, file_format TEXT NOT NULL,
            schema_version TEXT NOT NULL, state TEXT NOT NULL, row_count INTEGER,
            column_count INTEGER, profile_json TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES source(source_id),
            FOREIGN KEY(dataset_code) REFERENCES dataset(dataset_code)
        );

CREATE TABLE institution (
            tedt_institution_id TEXT PRIMARY KEY, official_id TEXT, official_id_issuer TEXT,
            id_status TEXT NOT NULL CHECK(id_status IN ('official_verified','provisional_internal','unresolved')),
            created_at TEXT NOT NULL, created_by TEXT NOT NULL,
            UNIQUE(official_id_issuer, official_id)
        );

CREATE TABLE institution_alias (
            alias_id TEXT PRIMARY KEY, tedt_institution_id TEXT NOT NULL, alias TEXT NOT NULL,
            language TEXT, valid_from TEXT, valid_to TEXT, source_id TEXT,
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id)
        );

CREATE TABLE institution_relation (
            relation_id TEXT PRIMARY KEY, from_institution_id TEXT NOT NULL,
            to_institution_id TEXT NOT NULL, relation_type TEXT NOT NULL,
            effective_date TEXT, source_id TEXT, justification TEXT,
            FOREIGN KEY(from_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(to_institution_id) REFERENCES institution(tedt_institution_id)
        );

CREATE TABLE institution_version (
            institution_version_id TEXT PRIMARY KEY, tedt_institution_id TEXT NOT NULL,
            name_fr TEXT, name_ar TEXT, institution_type TEXT, education_level TEXT,
            status TEXT, authority TEXT, governorate TEXT, delegation TEXT, geographic_sector TEXT,
            latitude REAL, longitude REAL, valid_from TEXT, valid_to TEXT,
            recorded_at TEXT NOT NULL, superseded_at TEXT, source_id TEXT, batch_id TEXT,
            change_reason TEXT,
            FOREIGN KEY(tedt_institution_id) REFERENCES institution(tedt_institution_id),
            FOREIGN KEY(source_id) REFERENCES source(source_id),
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE TABLE source (
            source_id TEXT PRIMARY KEY, source_name TEXT NOT NULL, owner TEXT NOT NULL,
            url TEXT, access_status INTEGER, access_conditions TEXT, reuse_conditions TEXT,
            verified_at TEXT, verification_note TEXT
        );

CREATE TABLE transformation_run (
            transformation_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, mapping_version TEXT NOT NULL,
            transformation_spec TEXT NOT NULL, actor TEXT NOT NULL, executed_at TEXT NOT NULL,
            status TEXT NOT NULL, output_sha256 TEXT,
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE TABLE validation_issue (
            issue_id INTEGER PRIMARY KEY AUTOINCREMENT, validation_id TEXT NOT NULL,
            severity TEXT NOT NULL, issue_code TEXT NOT NULL, column_name TEXT,
            row_number INTEGER, message TEXT NOT NULL,
            FOREIGN KEY(validation_id) REFERENCES validation_run(validation_id)
        );

CREATE TABLE validation_run (
            validation_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, rules_version TEXT NOT NULL,
            status TEXT NOT NULL, quality_json TEXT NOT NULL, run_at TEXT NOT NULL,
            FOREIGN KEY(batch_id) REFERENCES ingestion_batch(batch_id)
        );

CREATE INDEX idx_batch_source ON ingestion_batch(source_id, dataset_code);

CREATE INDEX idx_fact_indicator_period ON fact_observation(indicator_code, period_start, period_end);

CREATE INDEX idx_institution_official ON institution(official_id, official_id_issuer);
