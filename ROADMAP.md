# TeleDock Deployment Roadmap

## ✅ Completed
- [x] Database migrated (DigitalOcean → Neon.tech)
- [x] Deployed to server
- [x] Telegram userbot session regenerated
- [x] `/start`, `/admin`, `/myorders` commands working

## Phase 1: P2P Payment & SMS Flow
- [ ] Verify `/api/payments/sms-webhook` endpoint is reachable
- [ ] Test SMS parsing with real bank SMS format
- [ ] End-to-end P2P test: select product → pay → SMS → auto-approve
- [ ] Verify `orders.status` transitions: `pending` → `completed` correctly

## Phase 2: Userbot Fulfillment
- [ ] Confirm Telethon userbot can gift Telegram Stars
- [ ] Confirm userbot can gift Telegram Premium
- [ ] Test fulfillment after order is marked paid
- [ ] Add retry logic for failed fulfillments

## Phase 3: Payme / Click Integration
- [ ] Replace placeholder merchant credentials in `.env`
- [ ] Test Payme payment flow
- [ ] Test Click payment flow
- [ ] Verify callback/webhook handling

## Phase 4: Cleanup & Monitoring
- [ ] Stop old bot on DigitalOcean (if reachable)
- [ ] Add structured logging to bot handlers
- [ ] Set up basic healthcheck endpoint
- [ ] Add `FAILED` order retry button in admin panel

## Phase 5: Frontend Polish (Optional)
- [ ] Verify frontend at `teledock-frontend.netlify.app` connects to new API
- [ ] Test CORS with `API_BASE_URL`
