// webstack/src/components/VolumeChart.tsx
"use client";

import { useEffect, useRef } from 'react';
import { PriceDataPoint } from '@/src/lib/priceDataService';

type Props = {
  priceData: PriceDataPoint[];
  ticker: string;
  height?: number;
};

export default function VolumeChart({ 
  priceData, 
  ticker,
  height = 400 
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || priceData.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Chart margins
    const margin = { top: 20, right: 80, bottom: 40, left: 60 };
    const chartWidth = canvas.width - margin.left - margin.right;
    const chartHeight = canvas.height - margin.top - margin.bottom;

    // Data ranges
    const dates = priceData.map(d => d.date.getTime());
    const prices = priceData.map(d => d.price);
    const volumes = priceData.map(d => d.volume);
    
    const minDate = Math.min(...dates);
    const maxDate = Math.max(...dates);
    const minPrice = Math.min(...prices) * 0.95;
    const maxPrice = Math.max(...prices) * 1.05;
    const maxVolume = Math.max(...volumes);

    // Scaling functions
    const xScale = (date: number) => ((date - minDate) / (maxDate - minDate)) * chartWidth + margin.left;
    const yPriceScale = (price: number) => chartHeight - ((price - minPrice) / (maxPrice - minPrice)) * chartHeight + margin.top;

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

    // Draw volume bars
    const barWidth = Math.max(1, chartWidth / priceData.length * 0.8);
    
    priceData.forEach((point, index) => {
      const x = xScale(point.date.getTime());
      const barHeight = (point.volume / maxVolume) * (chartHeight * 0.3);
      const barY = canvas.height - margin.bottom - barHeight;
      
      // Volume bar color based on price change
      if (index > 0) {
        const prevPrice = priceData[index - 1].price;
        ctx.fillStyle = point.price > prevPrice ? 'var(--c-teal)' : 'var(--c-red)';
      } else {
        ctx.fillStyle = 'var(--c-gray)';
      }
      
      ctx.globalAlpha = 0.7;
      ctx.fillRect(x - barWidth/2, barY, barWidth, barHeight);
      ctx.globalAlpha = 1.0;
    });

    // Draw price line
    ctx.strokeStyle = 'var(--c-blue)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    priceData.forEach((point, index) => {
      const x = xScale(point.date.getTime());
      const y = yPriceScale(point.price);
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();

    // Draw price line with gradient
    const gradient = ctx.createLinearGradient(0, margin.top, 0, canvas.height - margin.bottom);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.2)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.05)');
    
    ctx.fillStyle = gradient;
    ctx.beginPath();
    
    priceData.forEach((point, index) => {
      const x = xScale(point.date.getTime());
      const y = yPriceScale(point.price);
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    // Close the path to bottom for gradient fill
    const lastX = xScale(priceData[priceData.length - 1].date.getTime());
    const firstX = xScale(priceData[0].date.getTime());
    ctx.lineTo(lastX, canvas.height - margin.bottom);
    ctx.lineTo(firstX, canvas.height - margin.bottom);
    ctx.closePath();
    ctx.fill();

    // Draw axes labels
    ctx.fillStyle = 'var(--c-gray)';
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

    // Y-axis labels (prices) - left side
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

    // Y-axis labels (volume) - right side
    ctx.textAlign = 'left';
    for (let i = 0; i <= 3; i++) {
      const volume = (maxVolume * (3 - i)) / 3;
      const y = canvas.height - margin.bottom - ((volume / maxVolume) * (chartHeight * 0.3));
      ctx.fillText(
        `${(volume / 1000000).toFixed(1)}M`,
        canvas.width - margin.right + 10,
        y + 4
      );
    }

    // Chart title
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 16px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${ticker} Price and Volume`, canvas.width / 2, 20);

    // Y-axis labels
    ctx.fillStyle = 'var(--c-gray)';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    
    // Price label (left)
    ctx.save();
    ctx.translate(15, canvas.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Price ($)', 0, 0);
    ctx.restore();
    
    // Volume label (right)
    ctx.save();
    ctx.translate(canvas.width - 15, canvas.height / 2);
    ctx.rotate(Math.PI / 2);
    ctx.fillText('Volume (M)', 0, 0);
    ctx.restore();

    // Handle mouse events for tooltips
    const handleMouseMove = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      
             // Find the closest data point
       const closestPoint = priceData.reduce((closest: PriceDataPoint | null, point) => {
         const pointX = xScale(point.date.getTime());
         const distance = Math.abs(x - pointX);
         
         if (distance < 20) {
           if (!closest) return point;
           
           const closestX = xScale(closest.date.getTime());
           const closestDistance = Math.abs(x - closestX);
           
           return distance < closestDistance ? point : closest;
         }
         
         return closest;
       }, null);
      
      const tooltip = tooltipRef.current;
      if (tooltip) {
        if (closestPoint) {
          tooltip.style.display = 'block';
          tooltip.style.left = `${event.clientX + 10}px`;
          tooltip.style.top = `${event.clientY - 10}px`;
          tooltip.innerHTML = `
            <div class="bg-gray-800 text-white p-2 rounded shadow-lg border border-gray-600 text-sm">
              <div class="font-semibold">${ticker}</div>
              <div class="text-blue-400">Price: $${closestPoint.price.toFixed(2)}</div>
              <div class="text-gray-400">Volume: ${(closestPoint.volume / 1000000).toFixed(1)}M</div>
              <div class="text-gray-400">${closestPoint.date.toLocaleDateString()}</div>
            </div>
          `;
        } else {
          tooltip.style.display = 'none';
        }
      }
    };

    const handleMouseLeave = () => {
      const tooltip = tooltipRef.current;
      if (tooltip) {
        tooltip.style.display = 'none';
      }
    };

    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [priceData, ticker, height]);

  const avgVolume = priceData.reduce((sum, p) => sum + p.volume, 0) / priceData.length;
  const currentPrice = priceData[priceData.length - 1]?.price || 0;
  const priceChange = priceData.length > 1 ? 
    currentPrice - priceData[priceData.length - 2].price : 0;

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xl font-bold text-white">Volume and Price Chart</h3>
        <div className="flex gap-6 text-sm">
          <div className="text-center">
            <div className="text-gray-400">Current Price</div>
            <div className={`font-semibold ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${currentPrice.toFixed(2)}
              <span className="ml-1">
                {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}
              </span>
            </div>
          </div>
          <div className="text-center">
            <div className="text-gray-400">Avg Volume</div>
            <div className="text-white font-semibold">
              {(avgVolume / 1000000).toFixed(1)}M
            </div>
          </div>
        </div>
      </div>
      
      <div ref={containerRef} className="relative w-full">
        <canvas 
          ref={canvasRef}
          className="w-full border border-gray-600 rounded cursor-crosshair"
          style={{ height: `${height}px` }}
        />
      </div>
      
      {/* Tooltip */}
      <div 
        ref={tooltipRef}
        className="absolute pointer-events-none z-10"
        style={{ display: 'none' }}
      />
      
      <div className="mt-4 text-sm text-gray-400">
        <p>• Hover over the chart to see detailed price and volume data</p>
        <p>• Green volume bars indicate price increase, red indicates decrease</p>
        <p>• Blue line shows price trend over time</p>
      </div>
    </div>
  );
} 