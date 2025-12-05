-- AlterTable
ALTER TABLE "SubsidyProgram" DROP COLUMN "bonusForExport",
DROP COLUMN "entityTypes",
DROP COLUMN "maxSpend",
DROP COLUMN "minSpend",
DROP COLUMN "requiresExport",
ADD COLUMN     "isExport" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "keywords" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
ADD COLUMN     "maxBudget" INTEGER,
ADD COLUMN     "minBudget" INTEGER,
ADD COLUMN     "sectors" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
DROP COLUMN "costTypes",
ADD COLUMN     "costTypes" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
DROP COLUMN "regions",
ADD COLUMN     "regions" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
ALTER COLUMN "coverageRate" DROP NOT NULL,
ALTER COLUMN "maxAmount" DROP NOT NULL;

