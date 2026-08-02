// Root Bicep template — full resources authored in Phase 9 (optional Azure deployment).
targetScope = 'resourceGroup'

param location string = resourceGroup().location
param environment string = 'dev'
