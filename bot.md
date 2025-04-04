# SharedInventory.bsky.social Bot

A bot on Bluesky that adds members' posts to a shared inventory of stuff.

## Overview
The bot monitors notifications for mentions, analyzes posts (text, images, videos), generates structured data, and adds items to a shared inventory database. Users can access this inventory through a web interface.

## Development Plan

### Phase 1: Core Bot Setup & Mention Monitoring (MVP)
- Set up project structure and environment
- Implement Bluesky API authentication
- Create notification polling system to detect mentions
- Add membership verification logic
- Implement automated responses for non-members
- Create basic data storage for members

### Phase 2: Content Analysis & Data Structuring
- Develop text analysis for posts
- Implement image recognition capabilities
- Add video content processing
- Create data extraction and categorization system
- Build robust database schema
- Implement CRUD operations for inventory items

### Phase 3: Web Interface Development
- Create web application with Bluesky authentication (DM verification)
- Develop user profile management
- Implement preference and location settings
- Build inventory browsing interface with search and filters
- Add notification system for inventory updates

## Functionality

**When mentioned:**
- The bot checks if user is a member
- If not, it replies with information on how to become a member
- For members, it analyzes the post content and adds items to the inventory

**Web Interface:**
- Users log in using their Bluesky account (verification via DM)
- Users can manage their profile information (location, preferences)
- Users can browse, search, and filter the shared inventory database

## Technical Requirements
- Bluesky API integration
- Content analysis capabilities (text, image, video)
- Secure authentication system
- Database for inventory management
- Web application framework
