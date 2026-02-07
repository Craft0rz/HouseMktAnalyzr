'use client';

import { useState, useEffect } from 'react';
import { Calculator, DollarSign, Percent, Home, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useQuickCalc, useMortgage } from '@/hooks/useProperties';

const formatPrice = (price: number) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(price);
};

export default function CalculatorPage() {
  const [price, setPrice] = useState<string>('500000');
  const [monthlyRent, setMonthlyRent] = useState<string>('3500');
  const [units, setUnits] = useState<string>('3');
  const [downPaymentPct, setDownPaymentPct] = useState<string>('20');
  const [interestRate, setInterestRate] = useState<string>('5');
  const [expenseRatio, setExpenseRatio] = useState<string>('35');

  const priceNum = parseInt(price) || 0;
  const rentNum = parseInt(monthlyRent) || 0;
  const unitsNum = parseInt(units) || 1;
  const downPct = (parseFloat(downPaymentPct) || 20) / 100;
  const intRate = (parseFloat(interestRate) || 5) / 100;
  const expRatio = (parseFloat(expenseRatio) || 35) / 100;

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
        <h1 className="text-3xl font-bold tracking-tight">Investment Calculator</h1>
        <p className="text-muted-foreground">
          Run quick what-if scenarios for investment properties
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Input Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calculator className="h-5 w-5" />
              Property Details
            </CardTitle>
            <CardDescription>Enter property information to calculate metrics</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Purchase Price ($)</label>
                <Input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="500000"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Monthly Rent ($)</label>
                <Input
                  type="number"
                  value={monthlyRent}
                  onChange={(e) => setMonthlyRent(e.target.value)}
                  placeholder="3500"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Units</label>
                <Input
                  type="number"
                  value={units}
                  onChange={(e) => setUnits(e.target.value)}
                  placeholder="3"
                  min="1"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Down Payment (%)</label>
                <Input
                  type="number"
                  value={downPaymentPct}
                  onChange={(e) => setDownPaymentPct(e.target.value)}
                  placeholder="20"
                  min="5"
                  max="100"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Interest Rate (%)</label>
                <Input
                  type="number"
                  value={interestRate}
                  onChange={(e) => setInterestRate(e.target.value)}
                  placeholder="5"
                  step="0.1"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Expense Ratio (%)</label>
                <Input
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
              Mortgage Details
            </CardTitle>
            <CardDescription>30-year amortization with semi-annual compounding</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {mortgageData ? (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground">Down Payment</div>
                  <div className="text-lg font-medium">{formatPrice(mortgageData.down_payment)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Loan Amount</div>
                  <div className="text-lg font-medium">{formatPrice(mortgageData.principal)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Monthly Payment</div>
                  <div className="text-lg font-medium">{formatPrice(mortgageData.monthly_payment)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Total Cash Needed</div>
                  <div className="text-lg font-medium">{formatPrice(mortgageData.total_cash_needed)}</div>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground text-center py-4">
                Enter property price to calculate mortgage
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
                Investment Metrics
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Cap Rate</span>
                <Badge variant="outline" className="text-lg">
                  {calcData.cap_rate.toFixed(2)}%
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Gross Yield</span>
                <Badge variant="outline" className="text-lg">
                  {calcData.gross_yield.toFixed(2)}%
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">GRM</span>
                <Badge variant="outline" className="text-lg">
                  {calcData.grm.toFixed(1)}
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Cash-on-Cash</span>
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
                Cash Flow
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-center py-4">
                <div className="text-sm text-muted-foreground">Monthly Cash Flow</div>
                <div className={`text-4xl font-bold ${calcData.monthly_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {calcData.monthly_cash_flow >= 0 ? '' : '-'}{formatPrice(Math.abs(calcData.monthly_cash_flow))}
                </div>
                <Badge
                  variant={calcData.monthly_cash_flow >= 0 ? 'default' : 'destructive'}
                  className="mt-2"
                >
                  {calcData.monthly_cash_flow >= 0 ? 'Positive Cash Flow' : 'Negative Cash Flow'}
                </Badge>
              </div>
              <Separator />
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Annual Cash Flow</span>
                <span className={calcData.annual_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}>
                  {formatPrice(calcData.annual_cash_flow)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">NOI (Net Operating Income)</span>
                <span>{formatPrice(calcData.noi)}</span>
              </div>
            </CardContent>
          </Card>

          {/* Per Unit */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Percent className="h-5 w-5" />
                Per Unit Analysis
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Price per Unit</span>
                <span className="font-medium">{formatPrice(calcData.price_per_unit)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Rent per Unit</span>
                <span className="font-medium">{formatPrice(rentNum / unitsNum)}/mo</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Cash Flow per Unit</span>
                <span className={`font-medium ${calcData.monthly_cash_flow >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatPrice(calcData.monthly_cash_flow / unitsNum)}/mo
                </span>
              </div>
              <Separator />
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Total Cash Required</span>
                <span className="font-medium">{formatPrice(calcData.total_cash_needed)}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {!calcData && priceNum > 0 && rentNum > 0 && calcLoading && (
        <div className="text-center py-8 text-muted-foreground">
          Calculating...
        </div>
      )}

      {(!priceNum || !rentNum) && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Enter a purchase price and monthly rent to see investment metrics
          </CardContent>
        </Card>
      )}
    </div>
  );
}
