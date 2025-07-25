-- CreateTable
CREATE TABLE "API_Requests" (
    "request_id" SERIAL NOT NULL,
    "filing_id" INTEGER NOT NULL,
    "doc_id" TEXT NOT NULL,
    "generation_id" TEXT,
    "model" TEXT NOT NULL,
    "max_tokens" INTEGER NOT NULL,
    "text_length" INTEGER NOT NULL,
    "approx_tokens" INTEGER NOT NULL,
    "finish_reason" TEXT,
    "response_status" INTEGER,
    "error_message" TEXT,
    "pdf_link" TEXT,
    "raw_text" TEXT,
    "llm_response" TEXT,
    "created_at" TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "API_Requests_pkey" PRIMARY KEY ("request_id")
);

-- CreateTable
CREATE TABLE "Assets" (
    "asset_id" SERIAL NOT NULL,
    "company_name" TEXT NOT NULL,
    "ticker" TEXT,
    "created_at" TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Assets_pkey" PRIMARY KEY ("asset_id")
);

-- CreateTable
CREATE TABLE "Filings" (
    "filing_id" SERIAL NOT NULL,
    "member_id" INTEGER NOT NULL,
    "doc_id" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "filing_date" TIMESTAMP(3),
    "verified" BOOLEAN DEFAULT false,
    "created_at" TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Filings_pkey" PRIMARY KEY ("filing_id")
);

-- CreateTable
CREATE TABLE "Members" (
    "member_id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "photo_url" TEXT,
    "party" TEXT,
    "state" TEXT,
    "chamber" TEXT,
    "created_at" TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Members_pkey" PRIMARY KEY ("member_id")
);

-- CreateTable
CREATE TABLE "Transactions" (
    "transaction_id" SERIAL NOT NULL,
    "filing_id" INTEGER NOT NULL,
    "asset_id" INTEGER NOT NULL,
    "owner_code" TEXT,
    "transaction_type" TEXT NOT NULL,
    "transaction_date" TIMESTAMP(3),
    "amount_range_low" DOUBLE PRECISION,
    "amount_range_high" DOUBLE PRECISION,
    "raw_llm_csv_line" TEXT,
    "created_at" TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Transactions_pkey" PRIMARY KEY ("transaction_id")
);

-- CreateTable
CREATE TABLE "StockPrices" (
    "id" SERIAL NOT NULL,
    "ticker" TEXT NOT NULL,
    "price_date" TIMESTAMP(3) NOT NULL,
    "open" DOUBLE PRECISION NOT NULL,
    "high" DOUBLE PRECISION NOT NULL,
    "low" DOUBLE PRECISION NOT NULL,
    "close" DOUBLE PRECISION NOT NULL,
    "volume" BIGINT NOT NULL,
    "adj_open" DOUBLE PRECISION,
    "adj_high" DOUBLE PRECISION,
    "adj_low" DOUBLE PRECISION,
    "adj_close" DOUBLE PRECISION,
    "adj_volume" BIGINT,
    "split_factor" DOUBLE PRECISION DEFAULT 1.0,
    "dividend" DOUBLE PRECISION DEFAULT 0.0,
    "created_at" TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3),

    CONSTRAINT "StockPrices_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "API_Requests_filing_id_idx" ON "API_Requests"("filing_id");

-- CreateIndex
CREATE INDEX "API_Requests_created_at_idx" ON "API_Requests"("created_at");

-- CreateIndex
CREATE INDEX "Assets_ticker_idx" ON "Assets"("ticker");

-- CreateIndex
CREATE INDEX "Assets_company_name_idx" ON "Assets"("company_name");

-- CreateIndex
CREATE UNIQUE INDEX "sqlite_autoindex_Assets_1" ON "Assets"("company_name", "ticker");

-- CreateIndex
CREATE UNIQUE INDEX "sqlite_autoindex_Filings_1" ON "Filings"("doc_id");

-- CreateIndex
CREATE INDEX "Filings_member_id_idx" ON "Filings"("member_id");

-- CreateIndex
CREATE INDEX "Filings_filing_date_idx" ON "Filings"("filing_date");

-- CreateIndex
CREATE INDEX "Filings_created_at_idx" ON "Filings"("created_at");

-- CreateIndex
CREATE UNIQUE INDEX "idx_members_name_nocase" ON "Members"("name");

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

-- CreateIndex
CREATE INDEX "StockPrices_ticker_idx" ON "StockPrices"("ticker");

-- CreateIndex
CREATE INDEX "StockPrices_price_date_idx" ON "StockPrices"("price_date");

-- CreateIndex
CREATE UNIQUE INDEX "unique_ticker_date" ON "StockPrices"("ticker", "price_date");

-- AddForeignKey
ALTER TABLE "API_Requests" ADD CONSTRAINT "API_Requests_filing_id_fkey" FOREIGN KEY ("filing_id") REFERENCES "Filings"("filing_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "Filings" ADD CONSTRAINT "Filings_member_id_fkey" FOREIGN KEY ("member_id") REFERENCES "Members"("member_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "Transactions" ADD CONSTRAINT "Transactions_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "Assets"("asset_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "Transactions" ADD CONSTRAINT "Transactions_filing_id_fkey" FOREIGN KEY ("filing_id") REFERENCES "Filings"("filing_id") ON DELETE NO ACTION ON UPDATE NO ACTION;
