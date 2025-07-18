-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_StockPrices" (
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
    "updated_at" DATETIME
);
INSERT INTO "new_StockPrices" ("adj_close", "adj_high", "adj_low", "adj_open", "adj_volume", "close", "created_at", "dividend", "high", "id", "low", "open", "price_date", "split_factor", "ticker", "updated_at", "volume") SELECT "adj_close", "adj_high", "adj_low", "adj_open", "adj_volume", "close", "created_at", "dividend", "high", "id", "low", "open", "price_date", "split_factor", "ticker", "updated_at", "volume" FROM "StockPrices";
DROP TABLE "StockPrices";
ALTER TABLE "new_StockPrices" RENAME TO "StockPrices";
CREATE INDEX "StockPrices_ticker_idx" ON "StockPrices"("ticker");
CREATE INDEX "StockPrices_price_date_idx" ON "StockPrices"("price_date");
CREATE UNIQUE INDEX "unique_ticker_date" ON "StockPrices"("ticker", "price_date");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE INDEX "API_Requests_filing_id_idx" ON "API_Requests"("filing_id");

-- CreateIndex
CREATE INDEX "API_Requests_created_at_idx" ON "API_Requests"("created_at");

-- CreateIndex
CREATE INDEX "Assets_ticker_idx" ON "Assets"("ticker");

-- CreateIndex
CREATE INDEX "Assets_company_name_idx" ON "Assets"("company_name");

-- CreateIndex
CREATE INDEX "Filings_member_id_idx" ON "Filings"("member_id");

-- CreateIndex
CREATE INDEX "Filings_filing_date_idx" ON "Filings"("filing_date");

-- CreateIndex
CREATE INDEX "Filings_created_at_idx" ON "Filings"("created_at");

-- CreateIndex
CREATE INDEX "Members_party_idx" ON "Members"("party");

-- CreateIndex
CREATE INDEX "Members_state_idx" ON "Members"("state");

-- CreateIndex
CREATE INDEX "Members_chamber_idx" ON "Members"("chamber");

-- CreateIndex
CREATE INDEX "Members_name_idx" ON "Members"("name");

-- CreateIndex
CREATE INDEX "Transactions_filing_id_idx" ON "Transactions"("filing_id");

-- CreateIndex
CREATE INDEX "Transactions_asset_id_idx" ON "Transactions"("asset_id");

-- CreateIndex
CREATE INDEX "Transactions_transaction_date_idx" ON "Transactions"("transaction_date");

-- CreateIndex
CREATE INDEX "Transactions_transaction_type_idx" ON "Transactions"("transaction_type");

-- CreateIndex
CREATE INDEX "Transactions_amount_range_low_idx" ON "Transactions"("amount_range_low");

-- CreateIndex
CREATE INDEX "Transactions_amount_range_high_idx" ON "Transactions"("amount_range_high");

-- CreateIndex
CREATE INDEX "Transactions_created_at_idx" ON "Transactions"("created_at");
