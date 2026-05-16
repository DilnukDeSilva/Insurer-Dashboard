import "dotenv/config";
import cors from "cors";
import express from "express";

const app = express();
const port = Number(process.env.PORT) || 3001;

app.use(cors());
app.use(express.json());

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", service: "insurer-dashboard-api" });
});

app.listen(port, () => {
  console.log(`API listening on http://localhost:${port}`);
});
