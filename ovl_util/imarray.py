import logging
import os
import imageio.v3 as iio
import numpy as np

from generated.formats.ovl.versions import is_ztuac

logging.getLogger('PIL').setLevel(logging.WARNING)


def reconstruct_z(im):
	"""Takes an array with 2 channels and adds a third channel"""
	h, w, d = im.shape
	assert d == 2
	im_rec = np.empty((h, w, 3), dtype=im.dtype)
	im_rec[:, :, :2] = im[:, :, :2]
	# convert to range +-1
	im_f = im.astype(np.float32) / 127 - 1.0
	# take pythagoras
	norm_xy = np.clip(np.linalg.norm(im_f[:, :, :2], axis=-1), 0.0, 1.0)
	# resulting z is in in 0,1 range, scale back to uint8 range
	im_rec[:, :, 2] = np.round(np.sqrt(1.0 - norm_xy) * 127 + 127)
	return im_rec


def flip_gb(im):
	"""Flips green and blue channels of image array"""
	im = im.copy()
	im[:, :, 1] = 255 - im[:, :, 1]
	im[:, :, 2] = 255 - im[:, :, 2]
	logging.debug(f"Flipped GB channels")
	return im


def flip_g(im):
	"""Flips green channel of image array"""
	im = im.copy()
	im[:, :, 1] = 255 - im[:, :, 1]
	logging.debug(f"Flipped G channel")
	return im


def check_any(iterable, string):
	"""Returns true if any of the entries of the iterable occur in string"""
	return any([i in string for i in iterable])


def has_vectors(png_name, compression):
	if "pnormaltexture" in png_name:
		# PZ uses BC5, so just RG
		if "BC5" in compression:
			return "G"
		# pnormaltexture - JWE2 uses RGBA, with no need to flip channels
		else:
			return False
	if check_any(("normaltexture", "playered_warpoffset"), png_name):
		return "GB"


# define additional functions for specific channel indices
channel_modes = {
	("RG_B_A", "RG"): reconstruct_z,
	("RG", "RG"): reconstruct_z
	}


def channel_iter(channels):
	ch_i = 0
	# get the channels to use in each chunk, eg. RG (2), B (1), ...
	ch_names = channels.split("_")
	for ch_name in ch_names:
		ch_count = len(ch_name)
		# define which channels to use from im
		ch_slice = slice(ch_i, ch_i + ch_count)
		yield ch_name, ch_slice
		# increment indices
		ch_i += ch_count


def split_png(png_file_path, ovl, compression=None):
	"""Fixes normals and splits channels of one PNG file if needed"""
	out_files = []
	flip = has_vectors(png_file_path, compression)
	channels = get_split_mode(png_file_path, compression)
	if is_ztuac(ovl):
		flip = False
	if flip or channels:
		logging.info(f"Splitting {png_file_path} into {channels} channels")
		im = imread(png_file_path)
		if flip == "GB":
			im = flip_gb(im)
		if flip == "G":
			im = flip_g(im)
		if not channels:
			# don't split at all, overwrite
			iio.imwrite(png_file_path, im, compress_level=2)
			out_files.append(png_file_path)
		else:
			path_basename, ext = os.path.splitext(png_file_path)
			for ch_name, ch_slice in channel_iter(channels):
				# get raw slice of im
				im_slice = im[:, :, ch_slice]
				# logging.debug(f"Image shape {im_slice.shape}")
				# is there an additional function to perform for this channel config and ch_i?
				function = channel_modes.get((channels, ch_name), None)
				if function is not None:
					im_slice = function(im_slice)
					# logging.debug(f"Image shape after function {im_slice.shape}")
				file_path = f"{path_basename}_{ch_name}{ext}"
				# if the last dimension (channels) is 1, remove it for single channel PNG
				iio.imwrite(file_path, np.squeeze(im_slice), compress_level=2)
				out_files.append(file_path)
			# remove the original PNG
			os.remove(png_file_path)
	else:
		out_files.append(png_file_path)
	return out_files


PZ_color_morphs = (
	"palbinobasecolourandmasktexture",
	"perythristicbasecolourandmasktexture",
	"pleucisticbasecolourandmasktexture",
	"pmelanisticbasecolourandmasktexture",
	"pxanthicbasecolourandmasktexture",
)


def get_split_mode(png_name, compression):
	# stores only two channels
	if check_any(("BC5",), compression):
		# JWE2 pyro
		if check_any(("pbaseaotexture", "proughnessaopackedtexturedetailbase"), png_name):
			return "R_G"
		# PZ normal maps
		else:
			return "RG"
	if check_any(
			(
				"pmossbasecolourroughnesspackedtexture", "ppackedtexture", "palbedoandroughnessdetail", "pnormaltexture",
				"pbasecolourtexture", "pbasecolourandmasktexture", "pdiffusetexture", *PZ_color_morphs
			), png_name):
		return "RGB_A"
	# JWE2 only
	if check_any(("pbasenormaltexture", "pgradheightarray"), png_name):
		return "RG_B_A"
	if check_any((
		"packedtexture", "playered_blendweights", "playered_diffusetexture", "playered_heighttexture", "playered_packedtexture", "playered_remaptexture", "scartexture", "samplertexture",
		"pspecularmaptexture", "pflexicolourmaskstexture", "pshellmap", "pfinalphatexture", "ppiebaldtexture",
		"pcavityroughnessdielectricarray"), png_name):
		return "R_G_B_A"


def imread(uri):
	# using pngs with palettes requires a conversion
	# print(iio.immeta(uri))
	return iio.imread(uri, mode="RGBA")


def join_png(path_basename, tmp_dir, compression=None):
	"""This finds and if required, creates, a png file that is ready for DDS conversion (arrays or flipped channels)"""
	ext = ".png"
	logging.debug(f"Looking for .png for {path_basename}")
	in_dir, basename = os.path.split(path_basename)
	basename = basename.lower()
	png_file_path = os.path.join(in_dir, f"{basename}.png")
	tmp_png_file_path = os.path.join(tmp_dir, f"{basename}.png")
	channels = get_split_mode(basename, compression)
	flip = has_vectors(basename, compression)
	# check if processing needs to be done
	if not flip and not channels:
		if not os.path.isfile(png_file_path):
			raise FileNotFoundError(f"{png_file_path} does not exist")
		logging.debug(f"Need not process {png_file_path}")
		return png_file_path
	# rebuild from channels
	if channels:
		logging.info(f"Joining {png_file_path} from {channels} channels")
		im = None
		for ch_name, ch_slice in channel_iter(channels):
			tile_png_path = f"{path_basename}_{ch_name}{ext}"
			tile = imread(tile_png_path)
			if im is None:
				im = np.zeros(tile.shape, dtype=np.uint8)
			else:
				assert im.shape == tile.shape, f"Tile shape of {tile_png_path} ({tile.shape}) does not match expected shape ({im.shape})"
			# take a slice, starting at the first channel of the tile
			im[:, :, ch_slice] = tile[:, :, 0:len(ch_name)]
	else:
		# non-tiled files that need fixes - normal maps without channel packing
		# just read the one input file
		im = imread(png_file_path)

	# flip channels
	if flip == "GB":
		im = flip_gb(im)
	if flip == "G":
		im = flip_g(im)

	# this is shared for all pngs that have to be read
	logging.debug(f"Writing output to {tmp_png_file_path}")
	iio.imwrite(tmp_png_file_path, im, compress_level=2)
	return tmp_png_file_path
