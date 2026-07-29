.DEFAULT_GOAL := help

DEV_PROJECT ?= homefin
DEV_SLOT ?= 0
DEV_PORT_BASE ?= 21000

export DEV_PROJECT
export DEV_SLOT
export DEV_PORT_BASE

.PHONY: help dev-env dev-check dev-config dev-up dev-restart dev-down dev-ps dev-logs \
	adminer-up adminer-down mail-up mail-down playwright-ui test-backend test-e2e \
	change-plan change-check test-change-policy test-ci-plan validate-compose

help:
	@echo "HomeFin local development"
	@echo ""
	@echo "  make dev-up [DEV_SLOT=0]       Start the core development stack"
	@echo "  make dev-down [DEV_SLOT=0]     Stop only this HomeFin instance"
	@echo "  make dev-restart               Recreate core application services"
	@echo "  make dev-ps                    Show this instance"
	@echo "  make dev-logs                  Show recent logs"
	@echo "  make dev-env                   Show deterministic project/port values"
	@echo "  make dev-check                 Check project ownership and core ports"
	@echo "  make dev-config                Validate rendered development Compose"
	@echo "  make adminer-up|adminer-down   Enable or stop Adminer on demand"
	@echo "  make mail-up|mail-down         Enable or stop Mailcatcher on demand"
	@echo "  make playwright-ui             Run Playwright UI on demand"
	@echo "  make test-backend              Run backend tests in an isolated project"
	@echo "  make test-e2e                  Run E2E tests in an isolated project"
	@echo "  make change-plan               Report the minimum change risk"
	@echo "  make change-check              Validate risk, context, and evidence"
	@echo "  make test-change-policy        Test the change policy checker"
	@echo "  make test-ci-plan              Test path/risk CI selection"
	@echo "  make validate-compose          Validate dev and intranet Compose files"
	@echo ""
	@echo "Default slot 0: frontend 21000, backend 21001."

dev-env:
	@bash scripts/dev.sh env

dev-check:
	@bash scripts/dev.sh check

dev-config:
	@bash scripts/dev.sh config

dev-up:
	@bash scripts/dev.sh up

dev-restart:
	@bash scripts/dev.sh restart

dev-down:
	@bash scripts/dev.sh down

dev-ps:
	@bash scripts/dev.sh status

dev-logs:
	@bash scripts/dev.sh logs

adminer-up:
	@bash scripts/dev.sh adminer-up

adminer-down:
	@bash scripts/dev.sh adminer-down

mail-up:
	@bash scripts/dev.sh mail-up

mail-down:
	@bash scripts/dev.sh mail-down

playwright-ui:
	@bash scripts/dev.sh playwright-ui

test-backend:
	@bash scripts/dev.sh test-backend

test-e2e:
	@bash scripts/dev.sh test-e2e

change-plan:
	@bash scripts/change-policy.sh

change-check:
	@bash scripts/change-policy.sh --check

test-change-policy:
	@bash scripts/test-change-policy.sh

test-ci-plan:
	@bash scripts/test-ci-plan.sh

validate-compose:
	@bash scripts/validate-compose.sh
