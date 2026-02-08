'use client';

import { useState } from 'react';
import { Calculator, DollarSign, Percent, Home, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { LoadingCard } from '@/components/LoadingCard';
import { useQuickCalc, useMortgage } from '@/hooks/useProperties';
import { formatPrice } from '@/lib/formatters';
import { useTranslation } from '@/i18n/LanguageContext';

export default function CalculatorPage() {
  const { t, locale } = useTranslation();
  const [price, setPrice] = useState<string>('500000');
  const [monthlyRent, setMonthlyRent] = useState<string>('3500');
  const [units, setUnits] = useState<string>('3');
  const [downPaymentPct, setDownPaymentPct] = useState<string>('20');
  const [interestRate, setInterestRate] = useState<string>('5');
  const [expenseRatio, setExpenseRatio] = useState<string>('40');

  const priceNum = parseInt(price) || 0;
  const rentNum = parseInt(monthlyRent) || 0;
  const unitsNum = parseInt(units) || 1;
  const downPct = (parseFloat(downPaymentPct) || 20) / 100;
  const intRate = (parseFloat(interestRate) || 5) / 100;
  const expRatio = (parseFloat(expenseRatio) || 40) / 100;

  const { data: calcData, isLoading: calcLoading } = useQuickCalc(
    priceNum > 0 && rentNum > 0
      ? {
          price: priceNum,
          monthly_rent: rentNum,
          units: unitsNum,
          down_payment_pct: downPct,
          interest_rate: intRate,
          expense_ratio: expRatio,
        }
      : null
  );

  const { data: mortgageData } = useMortgage(
    priceNum > 0
      ? {
          price: priceNum,
          down_payment_pct: downPct,
          interest_rate: intRate,
        }
      : null
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('calculator.title')}</h1>
        <p className="text-muted-foreground">
          {t('calculator.subtitle')}
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Input Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calculator className="h-5 w-5" />
              {t('calculator.propertyDetails')}
            </CardTitle>
            <CardDescription>{t('calculator.propertyDetailsDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label htmlFor="calc-price" className="text-sm font-medium">{t('calculator.purchasePrice')}</label>
                <Input
                  id="calc-price"
                  type="number"
                  step="10000"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="500000"
                  min="0"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="calc-rent" className="text-sm font-medium">{t('calculator.monthlyRent')}</label>
                <Input
                  id="calc-rent"
                  type="number"
                  step="100"
                  value={monthlyRent}
                  onChange={(e) => setMonthlyRent(e.target.value)}
                  placeholder="3500"
                  min="0"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="calc-units" className="text-sm font-medium">{t('calculator.units')}</label>
                <Input
                  id="calc-units"
                  type="number"
                  value={units}
                  onChange={(e) => setUnits(e.target.value)}
                  placeholder="3"
                  min="1"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="calc-down-payment" className="text-sm font-medium">{t('calculator.downPayment')}</label>
                <Input
                  id="calc-down-payment"
                  type="number"
                  value={downPaymentPct}
                  onChange={(e) => setDownPaymentPct(e.target.value)}
                  placeholder="20"
                  min="5"
                  max="100"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="calc-interest" className="text-sm font-medium">{t('calculator.interestRate')}</label>
                <Input
                  id="calc-interest"
                  type="number"
                  value={interestRate}
                  onChange={(e) => setInterestRate(e.target.value)}
                  placeholder="5"
                  step="0.1"
                  min="0"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="calc-expense" className="text-sm font-medium">{t('calculator.expenseRatio')}</label>
                <Input
                  id="calc-expense"
                  type="number"
                  value={expenseRatio}
                  onChange={(e) => setExpenseRatio(e.target.value)}
                  placeholder="35"
                  min="10"
                  max="60"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Mortgage Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Home className="h-5 w-5" />
              {t('calculator.mortgageDetails')}
            </CardTitle>
            <CardDescription>{t('calculator.mortgageDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {mortgageData ? (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground">{t('calculator.downPaymentLabel')}</div>
                  <div className="text-lg font-medium">{formatPrice(mortgageData.down_payment, locale)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">{t('calculator.loanAmount')}</div>
                  <div className="text-lg font-medium">{formatPrice(mortgageData.principal, locale)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">{t('calculator.monthlyPayment')}</div>
                  <div className="text-lg font-medium">{formatPrice(mortgageData.monthly_payment, locale)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">{t('calculator.totalCashNeeded')}</div>
                  <div className="text-lg font-medium">{formatPrice(mortgageData.total_cash_needed, locale)}</div>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground text-center py-4">
                {t('calculator.enterPrice')}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Results */}
      {calcData && (
        <div className="grid gap-6 md:grid-cols-3">
          {/* Key Metrics */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                {t('calculator.investmentMetrics')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">{t('calculator.capRate')}</span>
                <Badge variant="outline" className="text-lg">
                  {calcData.cap_rate.toFixed(2)}%
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">{t('calculator.grossYield')}</span>
                <Badge variant="outline" className="text-lg">
                  {calcData.gross_yield.toFixed(2)}%
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">{t('calculator.grm')}</span>
                <Badge variant="outline" className="text-lg">
                  {calcData.grm.toFixed(1)}
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">{t('calculator.cashOnCash')}</span>
                <Badge variant="outline" className="text-lg">
                  {calcData.cash_on_cash_return.toFixed(2)}%
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Cash Flow */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5" />
                {t('calculator.cashFlow')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-center py-4">
                <div className="text-sm text-muted-foreground">{t('calculator.monthlyCashFlow')}</div>
                <div className={`text-4xl font-bold ${calcData.monthly_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {calcData.monthly_cash_flow >= 0 ? '' : '-'}{formatPrice(Math.abs(calcData.monthly_cash_flow), locale)}
                </div>
                <Badge
                  variant={calcData.monthly_cash_flow >= 0 ? 'default' : 'destructive'}
                  className="mt-2"
                >
                  {calcData.monthly_cash_flow >= 0 ? t('calculator.positiveCashFlow') : t('calculator.negativeCashFlow')}
                </Badge>
              </div>
              <Separator />
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">{t('calculator.annualCashFlow')}</span>
                <span className={calcData.annual_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}>
                  {formatPrice(calcData.annual_cash_flow, locale)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">{t('calculator.noi')}</span>
                <span>{formatPrice(calcData.noi, locale)}</span>
              </div>
            </CardContent>
          </Card>

          {/* Per Unit */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Percent className="h-5 w-5" />
                {t('calculator.perUnitAnalysis')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">{t('calculator.pricePerUnit')}</span>
                <span className="font-medium">{formatPrice(calcData.price_per_unit, locale)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">{t('calculator.rentPerUnit')}</span>
                <span className="font-medium">{formatPrice(rentNum / unitsNum, locale)}{t('common.perMonth')}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">{t('calculator.cashFlowPerUnit')}</span>
                <span className={`font-medium ${calcData.monthly_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatPrice(calcData.monthly_cash_flow / unitsNum, locale)}{t('common.perMonth')}
                </span>
              </div>
              <Separator />
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">{t('calculator.totalCashRequired')}</span>
                <span className="font-medium">{formatPrice(calcData.total_cash_needed, locale)}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {!calcData && priceNum > 0 && rentNum > 0 && calcLoading && (
        <LoadingCard message={t('calculator.calculating')} description={t('calculator.calculatingDesc')} />
      )}

      {(!priceNum || !rentNum) && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            {t('calculator.enterPriceRent')}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
