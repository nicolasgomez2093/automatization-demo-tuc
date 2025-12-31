import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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
        primary_color="#ff0000",
        plan=PlanType.PRO,
        max_users=10,
        max_projects=50,
        features={
            "attendance": True,
            "expenses": True,
            "projects": True,
            "whatsapp": False
        }
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
        full_name="Test User",
        role=UserRole.ADMIN,
        is_active=True
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
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_my_organization(auth_headers, test_org):
    """Test getting current user's organization."""
    response = client.get("/api/organizations/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_org.id
    assert data["name"] == "Test Company"
    assert data["slug"] == "test-company"
    assert data["plan"] == "pro"


def test_get_organization_features(auth_headers, test_org):
    """Test getting organization features."""
    response = client.get("/api/organizations/features", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    assert data["features"]["attendance"] is True
    assert data["features"]["whatsapp"] is False
    assert data["plan"] == "pro"


def test_get_organization_stats(auth_headers, test_org):
    """Test getting organization statistics."""
    response = client.get("/api/organizations/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "usage" in data
    assert "limits" in data
    assert data["usage"]["users"] >= 1  # At least the test user
    assert data["limits"]["max_users"] == 10


def test_update_organization(auth_headers, test_org):
    """Test updating organization settings."""
    update_data = {
        "name": "Updated Company",
        "primary_color": "#00ff00"
    }
    response = client.put(
        "/api/organizations/me",
        headers=auth_headers,
        json=update_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Company"
    assert data["primary_color"] == "#00ff00"


def test_organization_isolation(test_org, setup_database):
    """Test that users from different organizations are isolated."""
    db = TestingSessionLocal()
    
    # Create second organization
    org2 = Organization(
        name="Other Company",
        slug="other-company",
        plan=PlanType.BASIC
    )
    db.add(org2)
    db.commit()
    
    # Create user in second org
    user2 = User(
        organization_id=org2.id,
        email="other@test.com",
        username="otheruser",
        hashed_password=get_password_hash("pass123"),
        role=UserRole.USER
    )
    db.add(user2)
    db.commit()
    db.close()
    
    # Login as user2
    response = client.post(
        "/api/auth/login",
        data={"username": "otheruser", "password": "pass123"}
    )
    token2 = response.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}
    
    # User2 should see their own org, not org1
    response = client.get("/api/organizations/me", headers=headers2)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == org2.id
    assert data["name"] == "Other Company"


def test_feature_check(test_org):
    """Test organization feature checking."""
    assert test_org.has_feature("attendance") is True
    assert test_org.has_feature("whatsapp") is False
    assert test_org.has_feature("nonexistent") is False


def test_limits_check(test_org):
    """Test organization limits checking."""
    assert test_org.can_add_user(5) is True
    assert test_org.can_add_user(10) is False
    assert test_org.can_add_project(49) is True
    assert test_org.can_add_project(50) is False
