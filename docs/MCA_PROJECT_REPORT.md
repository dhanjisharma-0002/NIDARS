# NIDARS — MCA Major Project Final Report Outline

**Project Title:** AI-Based North India Flood and Landslide Prediction with Disaster-Aware Safe Route Optimization Using Machine Learning and GIS  
**Academic Degree:** Master of Computer Applications (MCA)  
**Academic Year:** 2025–2026  

---

## Table of Contents

### Chapter 1 — Introduction
* 1.1 Background and Context
* 1.2 Motivation for Disaster Risk Management in North India
* 1.3 Project Overview: The NIDARS Platform
* 1.4 Objectives and Scope of the Project
* 1.5 Organization of the Report

### Chapter 2 — Literature Review & Existing Systems
* 2.1 Overview of Flood Prediction Methodologies (Hydrological vs. ML)
* 2.2 Landslide Susceptibility Mapping Approaches
* 2.3 Existing Disaster Navigation Systems and Limitations
* 2.4 Research Gap and Problem Justification

### Chapter 3 — Problem Statement
* 3.1 Geographic and Climatic Vulnerabilities of Northern India (JK, HP, UP, BR)
* 3.2 Compounding Dual Hazards (Floods and Rainfall-Induced Landslides)
* 3.3 Blind-Spot Navigation During Extreme Weather Events
* 3.4 Formal Problem Formulation

### Chapter 4 — Proposed System & Methodology
* 4.1 System Overview and Core Innovations
* 4.2 Modular Phase-Wise Architectural Strategy
* 4.3 Data Pipeline and Real Meteorological Grounding
* 4.4 Risk Integration and Penalty Formulation

### Chapter 5 — System Requirements & Specifications
* 5.1 Hardware Requirements
* 5.2 Software Requirements and Framework Stack
* 5.3 Functional Requirements
* 5.4 Non-Functional Requirements (Security, Performance, Reliability)

### Chapter 6 — System Design & Architecture
* 6.1 Multi-Tier Architecture Diagram
* 6.2 Component Design (Web, ML, GIS, Routing, Emergency, Admin)
* 6.3 Data Flow Diagrams (DFD Level 0, Level 1, Level 2)
* 6.4 Sequence Diagrams for Key User Flows

### Chapter 7 — Database Design
* 7.1 Entity-Relationship (ER) Diagram
* 7.2 Database Normalization (3NF)
* 7.3 Relational Schema and Indexing Strategy
* 7.4 Migration Management via Alembic

### Chapter 8 — Machine Learning Methodology
* 8.1 9-Feature Grounded Feature Engineering Schema
* 8.2 Flood Prediction Engine (Random Forest Architecture & Tuning)
* 8.3 Landslide Prediction Engine (Gradient Boosting & NASA Ground Truth)
* 8.4 Addressing Extreme Class Imbalance & Threshold Calibration (Phase 4.1)

### Chapter 9 — GIS & Spatial Risk Methodology
* 9.1 64-Station Meteorological Monitoring Grid
* 9.2 Combined Hazard Risk Formulation ($w_{\text{flood}} + w_{\text{landslide}} = 1.0$)
* 9.3 Risk Level Categorization (Low, Moderate, High, Critical)
* 9.4 GeoJSON RFC 7946 Compliance and Interactive Leaflet Rendering

### Chapter 10 — Safe Route Optimization
* 10.1 Road Network Querying via OSRM
* 10.2 Continuous Polyline Discretization (1.0 km Interval Sampling)
* 10.3 50 km Spatial Hazard Association Rule
* 10.4 Disaster Route Cost Optimization: $\text{Cost} = \text{Distance} + (\text{Distance} \times 10.0 \times \text{Average Risk})$

### Chapter 11 — Emergency Module
* 11.1 Real-Time Geolocation & Coordinate Input
* 11.2 Live Facility Discovery via Overpass QL (Hospitals, Police, Shelters)
* 11.3 Nearest vs. Safest Risk-Aware Facility Recommendation
* 11.4 Immediate Evacuation Routing Integration

### Chapter 12 — Admin Module & System Analytics
* 12.1 Role-Based Access Control and Security Isolation
* 12.2 Real-Time MySQL Aggregation Metrics
* 12.3 Interactive Chart.js Operational Visualizations
* 12.4 Audit Logging and Sensitive Data Concealment

### Chapter 13 — Implementation Details
* 13.1 Backend Implementation in Flask and Python 3.14
* 13.2 Frontend UI Implementation with Bootstrap 5 & Vanilla JS
* 13.3 RESTful API Endpoints
* 13.4 External API Integration and Controlled Error Handling

### Chapter 14 — Testing & Quality Assurance
* 14.1 Unit Testing Strategy
* 14.2 Integration and End-to-End Regression Testing (107 Tests)
* 14.3 Security & Role-Based Authorization Testing
* 14.4 Performance & Response Time Benchmarking

### Chapter 15 — Results & Discussion
* 15.1 ML Model Evaluation Metrics (ROC-AUC, F1, Recall, Precision)
* 15.2 Route Optimization Case Studies (Delhi-Shimla, Chandigarh-Manali)
* 15.3 Emergency Mode Facility Discovery Field Verification
* 15.4 System Usability and Performance Analysis

### Chapter 16 — Limitations & Constraints
* 16.1 Academic Research Prototype Boundary
* 16.2 Meteorological Spatial Resolution & Station Density Limits
* 16.3 Upstream Network and OpenStreetMap Data Dependencies

### Chapter 17 — Future Scope
* 17.1 Integration with Satellite Radar (Sentinel-1 SAR / InSAR)
* 17.2 Real-Time Crowdsourced Road Obstruction Reporting
* 17.3 Mobile Application Development (Flutter / React Native)
* 17.4 Official Integration with State Disaster Management Authorities

### Chapter 18 — Conclusion
* 18.1 Summary of Contributions
* 18.2 Fulfillment of Project Objectives
* 18.3 Concluding Remarks
