# CARBON ESG — Үнэгүй MVP deployment

## Сонгосон архитектур

- Frontend: Render Static Site (Next.js static export, CDN, HTTPS).
- API: Render Web Service, Python 3.12 / FastAPI, Free plan, Singapore region.
- Database: Neon PostgreSQL Free — одоогийн main код DB persistence ашиглахгүй. DATABASE_URL-г API-д холбох нь SQLAlchemy/Alembic migration болон tenant-safe persistence merge болсны дараа хийгдэнэ.
- Domain: Render-ийн үнэгүй onrender.com subdomain.

render.yaml нь хоёр Render service-ийг тодорхойлно. Blueprint sync хийхийн тулд Render-д GitHub repository эрх өгөх шаардлагатай. Нууц утга repository-д хадгалахгүй.

## Deploy хийх алхам

1. GitHub дээрх deployment PR-ийг review хийж, merge хийнэ.
2. Render Dashboard → New → Blueprint.
3. ssboroo/carbon-esg репозиторыг холбоод render.yaml-г сонгоно.
4. Frontend Static Site, API Web Service гэсэн хоёр service гарч ирэхийг шалгана. Хоёуланг нь Free plan-аар үүсгэнэ.
5. Deploy дууссаны дараа API /health болон frontend URL-г шалгана. Render hostname өөр байвал API service-ийн CORS_ORIGINS утгыг яг frontend-ийн https://...onrender.com origin болгон тохируулж redeploy хийнэ.
6. Frontend build environment-ийн NEXT_PUBLIC_API_URL утга API-ийн public URL болж тохируулагдсан эсэхийг шалгана.

Render-ийн Blueprint service names нь carbon-esg-web ба carbon-esg-api; хэрэв нэр аль хэдийн эзлэгдсэн бол render.yaml-д нэрийг өөрчилж дахин sync хийнэ.

## Neon PostgreSQL

1. Neon Console дээр Free project үүсгэнэ.
2. Байршил сонгох боломжтой бол Singapore region сонгоно.
3. DB migration-ууд production-ready болсон хойно pooled connection string-ийг Render API service-ийн Environment хэсэгт DATABASE_URL нэрээр secret байдлаар нэмнэ.
4. Connection string-ийг чат, GitHub, .env.example эсвэл commit-д бүү оруул.

Анхаарах нь: Энэ deployment PR нь Neon project үүсгэхгүй, DB schema/migration нэмэхгүй. Одоогийн API stateless тул database connection-ийг хэрэглэж буй мэтээр дүр эсгэхгүй.

## Үнэгүй plan-ийн хязгаарлалт

- Render Free web service 15 минут хүсэлтгүй бол унтарч, дараагийн хүсэлтээр ойролцоогоор нэг минут асааж болно.
- Render Free нь туршилт, preview зориулалттай; бодит customer production data-д тохирохгүй.
- Neon Free нь compute/storage/network quota-тай, compute idle үед scale-to-zero хийнэ.
- Vercel Hobby нь зөвхөн personal/non-commercial use тул арилжааны SaaS-ийн hosting сонголт болгож ашиглаагүй.

## Local checks

Frontend: cd apps/web && npm install && npm run typecheck && npm run build

API: cd apps/api && pip install -r requirements-dev.txt && pytest -q

Deployment бүрийн дараа:
- Frontend URL HTTPS-ээр нээгдэж байгаа эсэх.
- API /health 200 буцааж байгаа эсэх.
- Browser CORS console error байхгүй эсэх.
- API logs дээр startup/import error байхгүй эсэх.

## Release blockers (customer data авахын өмнө)

Authentication, organization membership/RLS, PostgreSQL persistence ба migrations, durable audit log, verified Mongolia emission-factor approval, Scope 2 location/market dual reporting, backups/restore drills, monitoring, rate limiting болон security review-ийг дуусгаж тусад нь баталгаажуулна.
