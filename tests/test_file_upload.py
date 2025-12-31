import pytest
import os
from io import BytesIO
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from PIL import Image
from app.core.database import Base, get_db
from app.models.organization import Organization, PlanType
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from main import app

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_org(setup_database):
    """Create a test organization."""
    db = TestingSessionLocal()
    org = Organization(
        name="Test Company",
        slug="test-company",
        plan=PlanType.PRO
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    db.close()
    return org


@pytest.fixture
def test_user(test_org):
    """Create a test user."""
    db = TestingSessionLocal()
    user = User(
        organization_id=test_org.id,
        email="test@test.com",
        username="testuser",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.USER
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def auth_headers(test_user):
    """Get authentication headers."""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_test_image():
    """Create a test image file."""
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes


def test_upload_single_file(auth_headers, test_org):
    """Test uploading a single file."""
    img_bytes = create_test_image()
    
    response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        data={"prefix": "test"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "url" in data
    assert "filename" in data
    assert data["original_filename"] == "test.jpg"
    assert f"org_{test_org.id}" in data["url"]


def test_upload_multiple_files(auth_headers, test_org):
    """Test uploading multiple files."""
    files = [
        ("files", ("test1.jpg", create_test_image(), "image/jpeg")),
        ("files", ("test2.jpg", create_test_image(), "image/jpeg")),
    ]
    
    response = client.post(
        "/api/files/upload-multiple",
        headers=auth_headers,
        files=files,
        data={"prefix": "project"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["total"] == 2
    assert data["successful"] >= 1
    assert len(data["files"]) == 2


def test_upload_invalid_file_type(auth_headers):
    """Test uploading invalid file type."""
    # Create a fake executable file
    fake_file = BytesIO(b"fake executable content")
    
    response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        files={"file": ("malware.exe", fake_file, "application/x-msdownload")}
    )
    
    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"].lower()


def test_upload_without_auth():
    """Test uploading without authentication."""
    img_bytes = create_test_image()
    
    response = client.post(
        "/api/files/upload",
        files={"file": ("test.jpg", img_bytes, "image/jpeg")}
    )
    
    assert response.status_code == 401


def test_file_isolation_between_orgs(setup_database):
    """Test that files are isolated between organizations."""
    db = TestingSessionLocal()
    
    # Create two organizations
    org1 = Organization(name="Org 1", slug="org-1", plan=PlanType.PRO)
    org2 = Organization(name="Org 2", slug="org-2", plan=PlanType.PRO)
    db.add_all([org1, org2])
    db.commit()
    
    # Create users for each org
    user1 = User(
        organization_id=org1.id,
        email="user1@test.com",
        username="user1",
        hashed_password=get_password_hash("pass123"),
        role=UserRole.USER
    )
    user2 = User(
        organization_id=org2.id,
        email="user2@test.com",
        username="user2",
        hashed_password=get_password_hash("pass123"),
        role=UserRole.USER
    )
    db.add_all([user1, user2])
    db.commit()
    db.close()
    
    # Login as user1 and upload file
    response = client.post(
        "/api/auth/login",
        data={"username": "user1", "password": "pass123"}
    )
    token1 = response.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}
    
    img_bytes = create_test_image()
    response = client.post(
        "/api/files/upload",
        headers=headers1,
        files={"file": ("test.jpg", img_bytes, "image/jpeg")}
    )
    assert response.status_code == 201
    file_url = response.json()["url"]
    assert f"org_{org1.id}" in file_url
    
    # Login as user2 and try to delete user1's file
    response = client.post(
        "/api/auth/login",
        data={"username": "user2", "password": "pass123"}
    )
    token2 = response.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}
    
    response = client.delete(
        f"/api/files/delete?file_url={file_url}",
        headers=headers2
    )
    # Should fail because file belongs to different org
    assert response.status_code == 403


def test_delete_file(auth_headers, test_org):
    """Test deleting a file."""
    # First upload a file
    img_bytes = create_test_image()
    response = client.post(
        "/api/files/upload",
        headers=auth_headers,
        files={"file": ("test.jpg", img_bytes, "image/jpeg")}
    )
    file_url = response.json()["url"]
    
    # Now delete it
    response = client.delete(
        f"/api/files/delete?file_url={file_url}",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()
