# START_GLOBALS
from generated.array import Array
from generated.base_struct import BaseStruct
from generated.formats.base.basic import Float
import numpy as np

# END_GLOBALS


class SegmentsReader(BaseStruct):

	# START_CLASS

	@classmethod
	def read_fields(cls, stream, instance):
		instance.io_start = stream.tell()
		num_bounds = np.max(instance.arg) + 1
		instance.mins = Array.from_stream(stream, instance.context, 0, None, (num_bounds, 3), Float)
		instance.scales = Array.from_stream(stream, instance.context, 0, None, (num_bounds, 3), Float)
		instance.io_size = stream.tell() - instance.io_start

	@classmethod
	def write_fields(cls, stream, instance):
		instance.io_start = stream.tell()
		Array.to_stream(instance.mins, stream, instance.context, 0, None, instance.mins.shape, Float)
		Array.to_stream(instance.scales, stream, instance.context, 0, None, instance.scales.shape, Float)
		instance.io_size = stream.tell() - instance.io_start

	@classmethod
	def get_fields_str(cls, instance, indent=0):
		return f"\nMins:\n{instance.mins}, \nScales:\n{instance.scales}"

