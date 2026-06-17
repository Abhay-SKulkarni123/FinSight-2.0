from django.db import models
from django.contrib.auth.models import User


class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlist')
    ticker = models.CharField(max_length=50)
    market = models.CharField(max_length=50)
    display_name = models.CharField(max_length=100, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'ticker')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} — {self.ticker}"


class UserPortfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolio_holdings')
    ticker = models.CharField(max_length=50)
    market = models.CharField(max_length=50)
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    cost_basis = models.DecimalField(max_digits=20, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'ticker')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} — {self.ticker} x{self.quantity}"


class ModelMetrics(models.Model):
    ticker = models.CharField(max_length=50)
    market_type = models.CharField(max_length=50, blank=True)
    rmse = models.FloatField()
    mae = models.FloatField()
    r2_score = models.FloatField(default=0.0)
    training_samples = models.IntegerField(default=0)
    trained_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-trained_at']
        indexes = [models.Index(fields=['ticker'])]

    def __str__(self):
        return f"{self.ticker} — RMSE: {self.rmse:.4f}"


class PredictionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='predictions', null=True, blank=True)
    ticker = models.CharField(max_length=50)
    market_type = models.CharField(max_length=50, blank=True)
    current_price = models.FloatField()
    predicted_price = models.FloatField()
    confidence = models.FloatField()
    timeline = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def price_change_pct(self):
        if self.current_price:
            return ((self.predicted_price - self.current_price) / self.current_price) * 100
        return 0