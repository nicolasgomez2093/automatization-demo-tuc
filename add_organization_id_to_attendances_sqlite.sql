-- Add organization_id column to attendances table (SQLite)
ALTER TABLE attendances ADD COLUMN organization_id INT NOT NULL DEFAULT 1;

-- Create index for better performance
CREATE INDEX idx_attendances_organization_id ON attendances(organization_id);
