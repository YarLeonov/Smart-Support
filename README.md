# Smart Support — VTB (Scibox + RAG по Excel FAQ)

KB автоматически сгенерирована из `smart_support_vtb_belarus_faq_final.xlsx`: создано статей — **201**.

## Запуск
```bash
docker compose up --build
# или для Win.

# бэк:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000 --app-dir backend

# фронт:
cd frontend
npm install
npm i -D @vitejs/plugin-react
npm run dev
```

## SciBox
Укажите:
```
SCIBOX_BASE_URL=https://llm.t1v.scibox.tech/v1
SCIBOX_API_KEY=мой апи
```
Клиент `RealSciboxClient` делает /chat/completions и возвращает JSON сущностей.
