"""
The three cost-bearing sources: FuelPurchase, TollTransaction, DriverExpense.
Trip logs (in core.py) are reference data — these three are what actually
carry a monetary `amount`, and are what the conservation invariant sums over.
"""
from sqlalchemy import Column, String, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class FuelPurchase(Base):
    __tablename__ = "fuel_purchases"

    fuel_id = Column(String, primary_key=True)
    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)  # decimal, not float — see
    # Architecture.md for why (float rounding errors are unacceptable for money)

    vehicle = relationship("Vehicle", back_populates="fuel_purchases")


class TollTransaction(Base):
    __tablename__ = "toll_transactions"

    toll_id = Column(String, primary_key=True)
    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)

    vehicle = relationship("Vehicle", back_populates="toll_transactions")


class DriverExpense(Base):
    __tablename__ = "driver_expenses"

    expense_id = Column(String, primary_key=True)
    driver_id = Column(String, ForeignKey("drivers.driver_id"), nullable=False)
    # vehicle_id and trip_id are BOTH nullable — this is intentional and important:
    # the whole point of this table is that these references are often missing.
    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"), nullable=True)
    trip_id = Column(String, ForeignKey("trips.trip_id"), nullable=True)
    expense_date = Column(Date, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
