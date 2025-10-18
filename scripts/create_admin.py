#!/usr/bin/env python3
"""
Script to create an admin user for the FundChain platform.

Usage:
    python backend/scripts/create_admin.py

This script will prompt for admin credentials and create a new admin user
in the database. Admin users have full access to the platform.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from werkzeug.security import generate_password_hash
from app import create_app
from models import db, User, RoleEnum

def create_admin_user():
    """Interactive script to create an admin user."""
    
    app = create_app()
    
    with app.app_context():
        print("=" * 50)
        print("FundChain Admin User Creation")
        print("=" * 50)
        
        # Get admin details
        email = input("Admin email: ").strip()
        if not email:
            print("Error: Email is required")
            return
            
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"Error: User with email '{email}' already exists")
            if existing_user.role == RoleEnum.admin:
                print("This user is already an admin.")
            else:
                print(f"This user exists with role: {existing_user.role.value}")
                upgrade = input("Do you want to upgrade this user to admin? (y/N): ").lower()
                if upgrade == 'y':
                    existing_user.role = RoleEnum.admin
                    db.session.commit()
                    print(f"User '{email}' has been upgraded to admin!")
                    return
            return
            
        full_name = input("Admin full name: ").strip()
        if not full_name:
            print("Error: Full name is required")
            return
            
        password = input("Admin password (min 8 characters): ").strip()
        if len(password) < 8:
            print("Error: Password must be at least 8 characters")
            return
            
        confirm_password = input("Confirm password: ").strip()
        if password != confirm_password:
            print("Error: Passwords do not match")
            return
        
        # Create admin user
        try:
            password_hash = generate_password_hash(password)
            admin_user = User(
                full_name=full_name,
                email=email,
                password_hash=password_hash,
                role=RoleEnum.admin
            )
            
            db.session.add(admin_user)
            db.session.commit()
            
            print("\n" + "=" * 50)
            print("✅ Admin user created successfully!")
            print("=" * 50)
            print(f"Email: {email}")
            print(f"Name: {full_name}")
            print(f"Role: admin")
            print(f"User ID: {admin_user.id}")
            print("\nYou can now login with these credentials.")
            print("=" * 50)
            
        except Exception as e:
            print(f"Error creating admin user: {e}")
            db.session.rollback()

if __name__ == "__main__":
    create_admin_user()