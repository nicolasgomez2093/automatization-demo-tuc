-- Add organization_id column to attendances table
ALTER TABLE attendances ADD COLUMN organization_id INT NOT NULL DEFAULT 1;

-- Add foreign key constraint
ALTER TABLE attendances ADD CONSTRAINT fk_attendances_organization_id 
FOREIGN KEY (organization_id) REFERENCES organizations(id);

-- Add index for better performance
CREATE INDEX idx_attendances_organization_id ON attendances(organization_id);
