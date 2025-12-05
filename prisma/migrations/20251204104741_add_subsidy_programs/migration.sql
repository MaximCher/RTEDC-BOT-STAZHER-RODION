-- CreateTable
CREATE TABLE "SubsidyProgram" (
    "id" SERIAL NOT NULL,
    "code" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "entityTypes" TEXT NOT NULL,
    "requiresExport" BOOLEAN NOT NULL DEFAULT false,
    "costTypes" TEXT NOT NULL,
    "regions" TEXT NOT NULL,
    "minSpend" INTEGER NOT NULL,
    "maxSpend" INTEGER,
    "coverageRate" DOUBLE PRECISION NOT NULL,
    "bonusForExport" DOUBLE PRECISION,
    "maxAmount" INTEGER NOT NULL,
    "conditions" TEXT,
    "recipient" TEXT,
    "docsRequired" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SubsidyProgram_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "SubsidyProgram_code_key" ON "SubsidyProgram"("code");
