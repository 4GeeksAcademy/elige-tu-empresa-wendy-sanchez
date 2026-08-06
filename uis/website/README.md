# website

Public website UI for HealthCore built with Next.js + TypeScript.

## Purpose

This app migrates and improves the corporate website from milestone 1, keeping the same visual identity while moving to reusable React components and typed content.

## Features

- Route `/` for the English corporate landing page.
- Route `/es` for the Spanish corporate landing page.
- All milestone 1 sections included: header, hero, services, why HealthCore, locations, contact, footer.
- Shared TypeScript models and content-driven rendering.
- Schema.org JSON-LD for MedicalOrganization and MedicalClinic.

## Run locally

```bash
cd uis/website
npm install
npm run dev
```

Open:
- http://localhost:3000/
- http://localhost:3000/es

## Validation

```bash
npm run typecheck
npm run lint
```
