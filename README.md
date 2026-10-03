# SmartCity ITPL — AI-Powered Urban Digital Twin

SmartCity ITPL is an AI-powered smart-city monitoring and optimization system designed to monitor urban conditions, forecast important city parameters, optimize traffic using multi-objective optimization, and visualize the results through an interactive 3D digital twin.

The system combines **Attention LSTM forecasting, MOPSO optimization, FastAPI, and Three.js** into a single smart-city platform.

---

## 🌆 Project Overview

Urban environments generate large amounts of data related to traffic, pollution, noise, weather, and congestion. Analyzing this data can help understand current city conditions and support better traffic and environmental management.

This project processes smart-city sensor data and performs four major tasks:

1. **Monitor** current urban conditions.
2. **Forecast** future conditions using an Attention LSTM model.
3. **Optimize** traffic using Multi-Objective Particle Swarm Optimization (MOPSO).
4. **Visualize** the city using an interactive 3D digital twin.

The final system provides a real-time-style replay of recorded city data through a FastAPI backend and an interactive Three.js frontend.

---

## 🎯 Objectives

- Monitor smart-city environmental and traffic parameters.
- Forecast future CO₂, noise, and congestion values.
- Avoid data leakage during model training.
- Identify important factors influencing the predicted parameters.
- Optimize traffic plans considering travel time and emissions.
- Visualize pollution hotspots dynamically.
- Display moving traffic in a 3D city environment.
- Provide interactive sensor information.
- Provide an API-based architecture for connecting AI models with the frontend.

---

## 🏗️ System Architecture

```text
                    SmartCity Dataset
                           │
                           ▼
                  Data Preparation
                           │
                           ▼
              Hourly Resampling & Cleaning
                           │
                           ▼
             Chronological Train/Val/Test
                           │
                           ▼
                  Attention LSTM
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        Future Forecasts          Feature Importance
              │
              ▼
             MOPSO
              │
              ▼
     Multi-Objective Traffic Plans
              │
              ▼
             FastAPI
              │
       ┌──────┴─────────┐
       ▼                ▼
  2D Dashboard     Three.js Frontend
                         │
                         ▼
                 3D Digital Twin
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       Sensors       Traffic Cars    Hotspots