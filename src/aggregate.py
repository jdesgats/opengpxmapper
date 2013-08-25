# These are aggregates used for downsampling, they are built on the same
# scheme as SQLite custom aggregates

class Middle:
  def __init__(self, min=float('+inf'), max=float('-inf')):
    self.min = min
    self.max = max
  def step(self, value):
    self.min = min(value, self.min)
    self.max = max(value, self.max)
  def finalize(self):
    # (min+max) / 2 does not work for some types (e.g. datetimes)
    return self.min + ((self.max - self.min) / 2)

class Avg:
  def __init__(self):
    self.sum = 0
    self.count = 0
  def step(self, value):
    self.sum += value
    self.count += 1
  def finalize(self):
    return self.sum / self.count

class Composite:
  def __init__(self, **kwargs):
    self.inner = kwargs
  def step(self, value):
    for k, acc in self.inner.items():
      acc.step(value[k])
  def finalize(self):
    return { k: acc.finalize() for k, acc in self.inner.items() }
