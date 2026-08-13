"""
Core entities: Vehicle, Trip, Driver.
These map directly to the boxes in the ER diagram in Architecture.md.
"""
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    vehicle_id = Column(String, primary_key=True)
    registration_no = Column(String, nullable=False)

    # These "relationship" lines don't create new columns — they let you
    # write python code like `some_vehicle.trips` to get all trips for
    # that vehicle, instead of writing a manual query every time.
    trips = relationship("Trip", back_populates="vehicle")
    fuel_purchases = relationship("FuelPurchase", back_populates="vehicle")
    toll_transactions = relationship("TollTransaction", back_populates="vehicle")


class Trip(Base):
    __tablename__ = "trips"

    trip_id = Column(String, primary_key=True)
    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    distance_km = Column(Numeric(10, 2), nullable=True)  # distance isn't money,
    # but Numeric is still fine here; float would also be acceptable for distance
    # specifically (our ER diagram note about decimal was about MONEY fields)

    vehicle = relationship("Vehicle", back_populates="trips")


class Driver(Base):
    __tablename__ = "drivers"

    driver_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
