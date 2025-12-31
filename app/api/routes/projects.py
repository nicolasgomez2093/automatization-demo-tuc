from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.user import User
from app.models.project import Project, ProjectProgress, ProjectStatus
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectProgressCreate, ProjectProgressResponse
)
from app.schemas.user import UserResponse
from app.api.deps import get_current_user, get_manager_user

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Create a new project."""
    project = Project(
        organization_id=current_user.organization_id,
        name=project_data.name,
        description=project_data.description,
        client_id=project_data.client_id,
        status=project_data.status,
        budget=project_data.budget,
        start_date=project_data.start_date,
        end_date=project_data.end_date
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return project


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    status: Optional[ProjectStatus] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List projects with filters."""
    query = db.query(Project)
    
    if status:
        query = query.filter(Project.status == status)
    if client_id:
        query = query.filter(Project.client_id == client_id)
    
    projects = query.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Update project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Delete project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    db.delete(project)
    db.commit()
    
    return None


# Project Progress endpoints
@router.post("/{project_id}/progress", response_model=ProjectProgressResponse)
async def add_project_progress(
    project_id: int,
    progress_data: ProjectProgressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Add progress update to a project."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.organization_id == current_user.organization_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    progress = ProjectProgress(
        project_id=project_id,
        description=progress_data.description,
        progress_percentage=progress_data.progress_percentage,
        images=progress_data.images or [],
        documents=progress_data.documents or [],
        notes=progress_data.notes,
        hours_worked=progress_data.hours_worked,
        created_by_id=current_user.id
    )
    
    # Update project progress to latest
    project.progress_percentage = progress_data.progress_percentage
    
    db.add(progress)
    db.commit()
    db.refresh(progress)
    
    return progress


@router.put("/{project_id}/progress/{progress_id}", response_model=ProjectProgressResponse)
async def update_project_progress(
    project_id: int,
    progress_id: int,
    progress_data: ProjectProgressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Update a progress update."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.organization_id == current_user.organization_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    progress = db.query(ProjectProgress).filter(
        ProjectProgress.id == progress_id,
        ProjectProgress.project_id == project_id
    ).first()
    
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress not found"
        )
    
    # Update progress fields
    progress.description = progress_data.description
    progress.progress_percentage = progress_data.progress_percentage
    progress.images = progress_data.images or []
    progress.documents = progress_data.documents or []
    progress.notes = progress_data.notes
    progress.hours_worked = progress_data.hours_worked
    
    # Update project progress to latest if this is the most recent progress
    latest_progress = db.query(ProjectProgress).filter(
        ProjectProgress.project_id == project_id
    ).order_by(ProjectProgress.created_at.desc()).first()
    
    if latest_progress and latest_progress.id == progress_id:
        project.progress_percentage = progress_data.progress_percentage
    
    db.commit()
    db.refresh(progress)
    
    return progress


@router.delete("/{project_id}/progress/{progress_id}")
async def delete_project_progress(
    project_id: int,
    progress_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Delete a progress update."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.organization_id == current_user.organization_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    progress = db.query(ProjectProgress).filter(
        ProjectProgress.id == progress_id,
        ProjectProgress.project_id == project_id
    ).first()
    
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress not found"
        )
    
    db.delete(progress)
    
    # Update project progress to the most recent remaining progress
    latest_progress = db.query(ProjectProgress).filter(
        ProjectProgress.project_id == project_id
    ).order_by(ProjectProgress.created_at.desc()).first()
    
    if latest_progress:
        project.progress_percentage = latest_progress.progress_percentage
    else:
        project.progress_percentage = 0
    
    db.commit()
    
    return {"message": "Progress deleted successfully"}


@router.get("/{project_id}/progress", response_model=List[ProjectProgressResponse])
async def list_project_progress(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List progress updates for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    progress_updates = db.query(ProjectProgress).filter(
        ProjectProgress.project_id == project_id
    ).order_by(ProjectProgress.created_at.desc()).offset(skip).limit(limit).all()
    
    return progress_updates


# Project Members endpoints
@router.post("/{project_id}/members/{user_id}", status_code=status.HTTP_201_CREATED)
async def assign_user_to_project(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Assign a user to a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if already assigned
    if user in project.members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already assigned to this project"
        )
    
    project.members.append(user)
    db.commit()
    
    return {"message": "User assigned successfully", "project_id": project_id, "user_id": user_id}


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_project(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_user)
):
    """Remove a user from a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user not in project.members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not assigned to this project"
        )
    
    project.members.remove(user)
    db.commit()
    
    return None


@router.get("/{project_id}/members", response_model=List[UserResponse])
async def list_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all members assigned to a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project.members


@router.get("/user/{user_id}", response_model=List[ProjectResponse])
async def list_user_projects(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all projects assigned to a user."""
    # Users can only see their own projects unless they're manager/admin
    if user_id != current_user.id and current_user.role.value not in ["superadmin", "admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user.assigned_projects
