-- CreateTable
CREATE TABLE "API_Requests" (
    "request_id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
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
    "created_at" DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "API_Requests_filing_id_fkey" FOREIGN KEY ("filing_id") REFERENCES "Filings" ("filing_id") ON DELETE NO ACTION ON UPDATE NO ACTION
);

-- CreateTable
CREATE TABLE "Assets" (
    "asset_id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "company_name" TEXT NOT NULL,
    "ticker" TEXT,
    "created_at" DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "Filings" (
    "filing_id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "member_id" INTEGER NOT NULL,
    "doc_id" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "filing_date" DATETIME,
    "verified" BOOLEAN DEFAULT false,
    "created_at" DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Filings_member_id_fkey" FOREIGN KEY ("member_id") REFERENCES "Members" ("member_id") ON DELETE NO ACTION ON UPDATE NO ACTION
);

-- CreateTable
CREATE TABLE "Members" (
    "member_id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL,
    "created_at" DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "Transactions" (
    "transaction_id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "filing_id" INTEGER NOT NULL,
    "asset_id" INTEGER NOT NULL,
    "owner_code" TEXT,
    "transaction_type" TEXT NOT NULL,
    "transaction_date" DATETIME,
    "amount_range_low" INTEGER,
    "amount_range_high" INTEGER,
    "raw_llm_csv_line" TEXT,
    "created_at" DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Transactions_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "Assets" ("asset_id") ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT "Transactions_filing_id_fkey" FOREIGN KEY ("filing_id") REFERENCES "Filings" ("filing_id") ON DELETE NO ACTION ON UPDATE NO ACTION
);

-- CreateIndex
Pragma writable_schema=1;
CREATE UNIQUE INDEX "sqlite_autoindex_Assets_1" ON "Assets"("company_name", "ticker");
Pragma writable_schema=0;

-- CreateIndex
Pragma writable_schema=1;
CREATE UNIQUE INDEX "sqlite_autoindex_Filings_1" ON "Filings"("doc_id");
Pragma writable_schema=0;

-- CreateIndex
CREATE UNIQUE INDEX "idx_members_name_nocase" ON "Members"("name");
