ALTER TABLE hl7_inbound_message ADD COLUMN sending_application TEXT NOT NULL DEFAULT '';
ALTER TABLE hl7_inbound_message ADD COLUMN sending_facility TEXT NOT NULL DEFAULT '';
ALTER TABLE hl7_inbound_message ADD COLUMN organization_id TEXT NOT NULL DEFAULT '';
ALTER TABLE hl7_inbound_message ADD COLUMN payload_digest TEXT NOT NULL DEFAULT '';

ALTER TABLE hl7_inbound_message DROP CONSTRAINT hl7_inbound_message_pkey;
ALTER TABLE hl7_inbound_message
    ADD PRIMARY KEY (sending_application, sending_facility, organization_id, message_control_id);
