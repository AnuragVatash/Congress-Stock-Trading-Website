-- CreateTable
CREATE TABLE "StockPrices" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "ticker" TEXT NOT NULL,
    "price_date" DATETIME NOT NULL,
    "open" REAL NOT NULL,
    "high" REAL NOT NULL,
    "low" REAL NOT NULL,
    "close" REAL NOT NULL,
    "volume" BIGINT NOT NULL,
    "adj_open" REAL,
    "adj_high" REAL,
    "adj_low" REAL,
    "adj_close" REAL,
    "adj_volume" BIGINT,
    "split_factor" REAL DEFAULT 1.0,
    "dividend" REAL DEFAULT 0.0,
    "created_at" DATETIME DEFAULT CURRENT_TIMESTAMP,
    "updated_at" DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- CreateIndex
CREATE INDEX "StockPrices_ticker_idx" ON "StockPrices"("ticker");

-- CreateIndex
CREATE INDEX "StockPrices_price_date_idx" ON "StockPrices"("price_date");

-- CreateIndex
CREATE UNIQUE INDEX "unique_ticker_date" ON "StockPrices"("ticker", "price_date");
