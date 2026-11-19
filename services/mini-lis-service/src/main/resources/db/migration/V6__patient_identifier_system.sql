ALTER TABLE external_patients ADD COLUMN identifier_system TEXT;

UPDATE external_patients
SET identifier_system = 'https://lab.local/mini-lis/organization/' || organization_id || '/patient'
WHERE identifier_system IS NULL;

ALTER TABLE external_patients ALTER COLUMN identifier_system SET NOT NULL;

ALTER TABLE external_patients DROP CONSTRAINT external_patients_external;

ALTER TABLE external_patients
    ADD CONSTRAINT external_patients_external UNIQUE (organization_id, identifier_system, external_id);
