"""
Importing all models here ensures SQLAlchemy's Base knows about every
table when we call Base.metadata.create_all() elsewhere — without this,
some tables could silently fail to get created.
"""
from app.models.core import Vehicle, Trip, Driver
from app.models.costs import FuelPurchase, TollTransaction, DriverExpense
from app.models.allocation import AllocationRun, Allocation
