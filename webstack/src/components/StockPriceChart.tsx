// webstack/src/components/StockPriceChart.tsx
"use client";

import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { PriceDataPoint, TradeDataPoint } from '@/src/lib/priceDataService';

type Props = {
  priceData: PriceDataPoint[];
  tradeData: TradeDataPoint[];
  ticker: string;
  height?: number;
  clickTarget?: 'member' | 'asset';
  assetId?: number;
};

export default function StockPriceChart({ 
  priceData, 
  tradeData, 
  ticker,
  height = 400,
  clickTarget = 'member',
  assetId
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || priceData.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Resolve CSS custom properties to actual colors (canvas can't interpret var(...))
    const styles = getComputedStyle(document.documentElement);
    const colorJade = (styles.getPropertyValue('--c-jade') || '#10b981').trim();
    const colorError = (styles.getPropertyValue('--c-error') || '#ef4444').trim();
    const colorNavyText = (styles.getPropertyValue('--c-navy') || '#0f172a').trim();

    // Set canvas size
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Chart margins
    const margin = { top: 20, right: 20, bottom: 40, left: 60 };
    const chartWidth = canvas.width - margin.left - margin.right;
    const chartHeight = canvas.height - margin.top - margin.bottom;

    // Data ranges
    const dates = priceData.map(d => d.date.getTime());
    const prices = priceData.map(d => d.price);
    const minDate = Math.min(...dates);
    const maxDate = Math.max(...dates);
    const minPrice = Math.min(...prices) * 0.95;
    const maxPrice = Math.max(...prices) * 1.05;

    // Scaling functions
    const xScale = (date: number) => ((date - minDate) / (maxDate - minDate)) * chartWidth + margin.left;
    const yScale = (price: number) => chartHeight - ((price - minPrice) / (maxPrice - minPrice)) * chartHeight + margin.top;

    // Draw background
    ctx.fillStyle = '#1f2937';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw grid lines
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 1;
    
    // Vertical grid lines (time)
    for (let i = 0; i <= 5; i++) {
      const x = margin.left + (chartWidth * i) / 5;
      ctx.beginPath();
      ctx.moveTo(x, margin.top);
      ctx.lineTo(x, canvas.height - margin.bottom);
      ctx.stroke();
    }

    // Horizontal grid lines (price)
    for (let i = 0; i <= 5; i++) {
      const y = margin.top + (chartHeight * i) / 5;
      ctx.beginPath();
      ctx.moveTo(margin.left, y);
      ctx.lineTo(canvas.width - margin.right, y);
      ctx.stroke();
    }

    // Draw price line as continuous path (avoid visual gaps under pins)
    ctx.strokeStyle = colorJade;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < priceData.length; i++) {
      const x = xScale(priceData[i].date.getTime());
      const y = yScale(priceData[i].price);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Restrict pins to visible date range
    const visibleTrades = tradeData.filter(trade => {
      const t = trade.date.getTime();
      return t >= minDate && t <= maxDate;
    });

    // Draw trade pins
    visibleTrades.forEach(trade => {
      const x = xScale(trade.date.getTime());
      const y = yScale(trade.price);
      
      // Pin size based on trade amount
      const pinSize = Math.max(6, Math.min(16, Math.sqrt(trade.amount / 1000)));
      
      if (trade.type === 'buy') {
        // Buy pin (green, above line, pointing down)
        ctx.fillStyle = colorJade;
        ctx.beginPath();
        ctx.moveTo(x, y - 15);
        ctx.lineTo(x - pinSize/2, y - 5);
        ctx.lineTo(x + pinSize/2, y - 5);
        ctx.closePath();
        ctx.fill();
        
        // Pin stick
        ctx.strokeStyle = colorJade;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, y - 5);
        ctx.lineTo(x, y);
        ctx.stroke();
      } else {
        // Sell pin (red, below line, pointing up)
        ctx.fillStyle = colorError;
        ctx.beginPath();
        ctx.moveTo(x, y + 15);
        ctx.lineTo(x - pinSize/2, y + 5);
        ctx.lineTo(x + pinSize/2, y + 5);
        ctx.closePath();
        ctx.fill();
        
        // Pin stick
        ctx.strokeStyle = colorError;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, y + 5);
        ctx.lineTo(x, y);
        ctx.stroke();
      }
    });

    // Draw axes labels
    ctx.fillStyle = colorNavyText;
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    
    // X-axis labels (dates)
    for (let i = 0; i <= 5; i++) {
      const date = new Date(minDate + ((maxDate - minDate) * i) / 5);
      const x = margin.left + (chartWidth * i) / 5;
      ctx.fillText(
        date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        x,
        canvas.height - 10
      );
    }

    // Y-axis labels (prices)
    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const price = minPrice + ((maxPrice - minPrice) * (5 - i)) / 5;
      const y = margin.top + (chartHeight * i) / 5;
      ctx.fillText(
        `$${price.toFixed(2)}`,
        margin.left - 10,
        y + 4
      );
    }

    // Chart title
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 16px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${ticker} Stock Price with Congressional Trades`, canvas.width / 2, 20);

    // Helper to find hovered trade near cursor
    const findHoveredTrade = (x: number, y: number) => {
      return visibleTrades.find(trade => {
        const tradeX = xScale(trade.date.getTime());
        const tradeY = yScale(trade.price);
        return Math.abs(x - tradeX) < 10 && Math.abs(y - tradeY) < 20;
      }) || null;
    };

    // Handle mouse events for tooltips & cursor
    const handleMouseMove = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const hoveredTrade = findHoveredTrade(x, y);
      
      const tooltip = tooltipRef.current;
      if (tooltip) {
        if (hoveredTrade) {
          tooltip.style.display = 'block';
          tooltip.style.left = `${x + 10}px`;
          tooltip.style.top = `${y - 10}px`;
          tooltip.innerHTML = `
            <div class="bg-gray-800 text-white p-2 rounded shadow-lg border border-gray-600 text-sm">
              <div class="font-semibold">${hoveredTrade.memberName}</div>
              <div class="${hoveredTrade.type === 'buy' ? 'text-green-400' : 'text-red-400'}">
                ${hoveredTrade.type.toUpperCase()}: $${hoveredTrade.amount.toLocaleString()}
              </div>
              <div class="text-gray-400">${hoveredTrade.date.toLocaleDateString()}</div>
              <div class="text-gray-400">Price: $${hoveredTrade.price.toFixed(2)}</div>
            </div>
          `;
          canvas.style.cursor = 'pointer';
        } else {
          tooltip.style.display = 'none';
          canvas.style.cursor = 'crosshair';
        }
      }
    };

    const handleMouseLeave = () => {
      const tooltip = tooltipRef.current;
      if (tooltip) {
        tooltip.style.display = 'none';
      }
      canvas.style.cursor = 'crosshair';
    };

    const handleClick = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const hoveredTrade = findHoveredTrade(x, y);
      if (hoveredTrade) {
        if (clickTarget === 'asset' && typeof assetId === 'number') {
          router.push(`/stocks/${assetId}`);
        } else if (hoveredTrade.memberId) {
          router.push(`/members/${hoveredTrade.memberId}`);
        }
      }
    };

    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseleave', handleMouseLeave);
    canvas.addEventListener('click', handleClick);

    return () => {
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseleave', handleMouseLeave);
      canvas.removeEventListener('click', handleClick);
    };
  }, [priceData, tradeData, ticker, height, clickTarget, assetId, router]);

  const totalBuys = tradeData.filter(t => t.type === 'buy').length;
  const totalSells = tradeData.filter(t => t.type === 'sell').length;
  const totalVolume = tradeData.reduce((sum, t) => sum + t.amount, 0);

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xl font-bold text-white">Price Chart with Congressional Trades</h3>
        <div className="flex gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 transform rotate-45"></div>
            <span className="text-gray-300">{totalBuys} Buys</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-red-500 transform rotate-45"></div>
            <span className="text-gray-300">{totalSells} Sells</span>
          </div>
          <div className="text-gray-300">
            Total Volume: ${totalVolume.toLocaleString()}
          </div>
        </div>
      </div>
      
      <div ref={containerRef} className="relative w-full">
        <canvas 
          ref={canvasRef}
          className="w-full border border-gray-600 rounded cursor-crosshair"
          style={{ height: `${height}px` }}
        />
        {/* Tooltip (positioned relative to container) */}
        <div 
          ref={tooltipRef}
          className="absolute pointer-events-none z-10"
          style={{ display: 'none' }}
        />
      </div>
      
      <div className="mt-4 text-sm text-gray-400">
        <p>• Hover over pins to see trade details</p>
        <p>• Green pins (↓) represent purchases above the price line</p>
        <p>• Red pins (↑) represent sales below the price line</p>
        <p>• Pin size indicates trade volume</p>
      </div>
    </div>
  );
} 