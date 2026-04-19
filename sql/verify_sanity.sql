DO $$
DECLARE
    actual_count INTEGER;
    mismatch_details TEXT;
BEGIN
    SELECT count(*) INTO actual_count FROM projects;
    IF actual_count <> 14 THEN
        RAISE EXCEPTION 'projects count mismatch: expected 14, found %', actual_count;
    END IF;

    SELECT count(*) INTO actual_count FROM kill_criteria_templates;
    IF actual_count <> 6 THEN
        RAISE EXCEPTION 'kill_criteria_templates count mismatch: expected 6, found %', actual_count;
    END IF;

    SELECT count(*) INTO actual_count FROM project_state;
    IF actual_count <> 14 THEN
        RAISE EXCEPTION 'project_state count mismatch: expected 14, found %', actual_count;
    END IF;

    WITH expected(project_id, project_state_code) AS (
        VALUES
            ('ashrise', 1),
            ('procurement-core', 1),
            ('procurement-licitaciones', 1),
            ('procurement-aduana', 3),
            ('neytiri', 3),
            ('exreply', 4),
            ('osla', 5),
            ('osla-ashrise-integration', 5),
            ('osla-learning', 5),
            ('osla-small-qw', 5),
            ('osla-medium-long', 5),
            ('osla-unicorns', 5),
            ('osla-profound-ai', 5),
            ('osla-continue-search', 5)
    ),
    mismatches AS (
        SELECT
            COALESCE(expected.project_id, actual.project_id) AS project_id,
            expected.project_state_code AS expected_code,
            actual.project_state_code AS actual_code
        FROM expected
        FULL OUTER JOIN project_state AS actual
            ON actual.project_id = expected.project_id
        WHERE expected.project_id IS NULL
           OR actual.project_id IS NULL
           OR actual.project_state_code IS DISTINCT FROM expected.project_state_code
    )
    SELECT string_agg(
        format(
            '%s expected=%s actual=%s',
            project_id,
            COALESCE(expected_code::TEXT, '<missing>'),
            COALESCE(actual_code::TEXT, '<missing>')
        ),
        E'\n'
    )
    INTO mismatch_details
    FROM mismatches;

    IF mismatch_details IS NOT NULL THEN
        RAISE EXCEPTION 'project_state_code mismatch:%', E'\n' || mismatch_details;
    END IF;
END;
$$ LANGUAGE plpgsql;

SELECT 'verify_sanity passed' AS status;
