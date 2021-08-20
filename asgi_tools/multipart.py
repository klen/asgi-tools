"""The code is based on a great work of Andrew Dunham
(https://github.com/andrew-d/python-multipart) and has been changed to improve speed.

The original code is licensed by Apache2 license.
"""
import typing as t

# Flags for the multipart parser.
FLAG_PART_BOUNDARY              = 1
FLAG_LAST_BOUNDARY              = 2

# Get constants.  Since iterating over a str on Python 2 gives you a 1-length
# string, but iterating over a bytes object on Python 3 gives you an integer,
# we need to save these constants.
AMPERSAND = b'&'[0]
COLON = b':'[0]
CR = b'\r'[0]
EQUAL = b'='[0]
HYPHEN = b'-'[0]
LF = b'\n'[0]
SEMICOLON = b';'[0]
SPACE = b' '[0]
EMPTY = b'\x00'[0]


class BaseParser:
    """This class is the base class for all parsers.  It contains the logic for
    calling and adding callbacks.

    A callback can be one of two different forms.  "Notification callbacks" are
    callbacks that are called when something happens - for example, when a new
    part of a multipart message is encountered by the parser.  "Data callbacks"
    are called when we get some sort of data - for example, part of the body of
    a multipart chunk.  Notification callbacks are called with no parameters,
    whereas data callbacks are called with three, as follows::

        data_callback(data, start, end)

    The "data" parameter is a bytestring. "start" and "end" are integer indexes into the "data"
    string that represent the data of interest.  Thus, in a data callback, the slice
    `data[start:end]` represents the data that the callback is "interested in".  The callback is
    not passed a copy of the data, since copying severely hurts performance.

    """

    __slots__ = 'callbacks',

    def __init__(self, callbacks: t.Dict):
        self.callbacks = callbacks

    def callback(self, name: str, data: bytes, start: int, end: int):
        try:
            func = self.callbacks[name]
            func(data, start, end)
        except KeyError:
            pass

    def write(self, data: bytes):
        pass

    def finalize(self):
        pass


STATE_BEFORE_FIELD = 0
STATE_FIELD_NAME = 1
STATE_FIELD_DATA = 2


class QueryStringParser(BaseParser):
    """this is a streaming querystring parser.  it will consume data, and call
    the callbacks given when it has data.

    .. list-table::
       :widths: 15 10 30
       :header-rows: 1

       * - callback name
         - parameters
         - description
       * - field_start
         - none
         - called when a new field is encountered.
       * - field_name
         - data, start, end
         - called when a portion of a field's name is encountered.
       * - field_data
         - data, start, end
         - called when a portion of a field's data is encountered.
       * - field_end
         - none
         - called when the end of a field is encountered.
       * - end
         - none
         - called when the parser is finished parsing all data.

    :param callbacks: a dictionary of callbacks.  see the documentation for
                      :class:`baseparser`.

    :param max_size: the maximum size of body to parse.  defaults to 0
    """

    __slots__ = 'callbacks', 'cursize', 'max_size', 'state'

    def __init__(self, callbacks: t.Dict, max_size: int = 0):
        self.callbacks = callbacks
        self.cursize = 0
        self.max_size = max_size

        self.state = STATE_BEFORE_FIELD

    def write(self, data: bytes):
        data_len = prune_data(len(data), self.cursize, self.max_size)

        idx = 0
        state = self.state

        while idx < data_len:
            ch = data[idx]
            if state == STATE_BEFORE_FIELD:

                if not (ch == AMPERSAND or ch == SEMICOLON):
                    self.callback('field_start', b'', 0, 0)
                    idx -= 1
                    state = STATE_FIELD_NAME

            elif state == STATE_FIELD_NAME:
                sep_pos = data.find(AMPERSAND, idx)
                if sep_pos == -1:
                    sep_pos = data.find(SEMICOLON, idx)

                if sep_pos != -1:
                    equals_pos = data.find(EQUAL, idx, sep_pos)
                else:
                    equals_pos = data.find(EQUAL, idx)

                if equals_pos != -1:
                    self.callback('field_name', data, idx, equals_pos)
                    idx = equals_pos
                    state = STATE_FIELD_DATA

                else:
                    if sep_pos == -1:
                        self.callback('field_name', data, idx, data_len)
                        idx = data_len

                    else:
                        self.callback('field_name', data, idx, sep_pos)
                        self.callback('field_end', b'', 0, 0)
                        idx = sep_pos - 1
                        state = STATE_BEFORE_FIELD

            elif state == STATE_FIELD_DATA:
                sep_pos = data.find(AMPERSAND, idx)
                if sep_pos == -1:
                    sep_pos = data.find(SEMICOLON, idx)

                if sep_pos == -1:
                    self.callback('field_data', data, idx, data_len)
                    idx = data_len

                else:
                    self.callback('field_data', data, idx, sep_pos)
                    self.callback('field_end', b'', 0, 0)

                    idx = sep_pos - 1
                    state = STATE_BEFORE_FIELD

            else:
                raise ValueError(f"Reached an unknown state {state} at {idx}")

            idx += 1

        self.state = state
        self.cursize += data_len

    def finalize(self):
        """Finalize this parser, which signals to that we are finished parsing,
        if we're still in the middle of a field, an on_field_end callback, and
        then the on_end callback.
        """
        # If we're currently in the middle of a field, we finish it.
        if self.state == STATE_FIELD_DATA:
            self.callback('field_end', b'', 0, 0)
        self.callback('end', b'', 0, 0)


STATE_START                     = 0
STATE_START_BOUNDARY            = 1
STATE_HEADER_FIELD_START        = 2
STATE_HEADER_FIELD              = 3
STATE_HEADER_VALUE_START        = 4
STATE_HEADER_VALUE              = 5
STATE_HEADER_VALUE_ALMOST_DONE  = 6
STATE_HEADERS_ALMOST_DONE       = 7
STATE_PART_DATA_START           = 8
STATE_PART_DATA                 = 9
STATE_PART_DATA_END             = 10
STATE_END                       = 11


class MultipartParser(BaseParser):
    """This class is a streaming multipart/form-data parser.

    .. list-table::
       :widths: 15 10 30
       :header-rows: 1

       * - Callback Name
         - Parameters
         - Description
       * - part_begin
         - None
         - Called when a new part of the multipart message is encountered.
       * - part_data
         - data, start, end
         - Called when a portion of a part's data is encountered.
       * - part_end
         - None
         - Called when the end of a part is reached.
       * - header_begin
         - None
         - Called when we've found a new header in a part of a multipart
           message
       * - header_field
         - data, start, end
         - Called each time an additional portion of a header is read (i.e. the
           part of the header that is before the colon; the "Foo" in
           "Foo: Bar").
       * - header_value
         - data, start, end
         - Called when we get data for a header.
       * - header_end
         - None
         - Called when the current header is finished - i.e. we've reached the
           newline at the end of the header.
       * - headers_finished
         - None
         - Called when all headers are finished, and before the part data
           starts.
       * - end
         - None
         - Called when the parser is finished parsing all data.


    :param boundary: The multipart boundary.  This is required, and must match
                     what is given in the HTTP request - usually in the
                     Content-Type header.

    :param callbacks: A dictionary of callbacks.  See the documentation for
                      :class:`BaseParser`.

    :param max_size: The maximum size of body to parse.  Defaults to 0

    """

    __slots__ = (
        'callbacks', 'cursize', 'max_size', 'state', 'index', 'flags', 'header_field_pos',
        'header_value_pos', 'part_data_pos', 'boundary', 'boundary_chars', 'lookbehind')

    def __init__(self, boundary, callbacks: t.Dict, max_size: int = 0):
        self.callbacks = callbacks
        self.cursize = 0
        self.max_size = max_size
        self.state = STATE_START
        self.index = self.flags = 0

        self.header_field_pos = -1
        self.header_value_pos = -1
        self.part_data_pos = -1

        if isinstance(boundary, str):
            boundary = boundary.encode('latin-1')

        self.boundary = b'\r\n--' + boundary

        # Get a set of characters that belong to our boundary.
        self.boundary_chars = frozenset(self.boundary)

        # We also create a lookbehind list.
        # Note: the +8 is since we can have, at maximum, "\r\n--" + boundary +
        # "--\r\n" at the final boundary, and the length of '\r\n--' and
        # '--\r\n' is 8 bytes.
        self.lookbehind = [EMPTY for x in range(len(boundary) + 8)]

    def write(self, data):  # noqa
        data_len = prune_data(len(data), self.cursize, self.max_size)

        idx = 0
        index = self.index
        state = self.state
        flags = self.flags
        boundary = self.boundary
        boundary_len = len(boundary)

        while idx < data_len:
            ch = data[idx]

            if state == STATE_START_BOUNDARY:
                # Check to ensure that the last 2 characters in our boundary
                # are CRLF.
                if index == boundary_len - 2:
                    if ch != CR:
                        raise ValueError(f"Did not find \\r at end of boundary ({idx})")
                    index += 1

                elif index == boundary_len - 2 + 1:
                    if ch != LF:
                        raise ValueError(f"Did not find \\n at end of boundary ({idx})")

                    state = STATE_HEADER_FIELD_START
                    self.callback('part_begin', b'', 0, 0)

                # Check to ensure our boundary matches
                elif ch == boundary[index + 2]:
                    # Increment index into boundary and continue.
                    index += 1

                else:
                    raise ValueError(f"Did not find boundary character {chr(ch)} at index {idx}")

            elif state == STATE_HEADER_FIELD_START:
                # Mark the start of a header field here, reset the index, and
                # continue parsing our header field.
                index = 0
                self.header_field_pos = idx
                idx -= 1
                state = STATE_HEADER_FIELD

            elif state == STATE_HEADER_FIELD:
                # If we've reached a CR at the beginning of a header, it means
                # that we've reached the second of 2 newlines, and so there are
                # no more headers to parse.
                if ch == CR:
                    self.header_field_pos = -1
                    state = STATE_HEADERS_ALMOST_DONE
                    idx += 1
                    continue

                index += 1

                # If we've reached a colon, we're done with this header.
                if ch == COLON:
                    # A 0-length header is an error.
                    if index == 1:
                        raise ValueError(f"Found 0-length header at {idx}")

                    # Call our callback with the header field.
                    if self.header_field_pos != -1:
                        self.callback('header_field', data, self.header_field_pos, idx)
                        self.header_field_pos = -1

                    # Move to parsing the header value.
                    state = STATE_HEADER_VALUE_START

            elif state == STATE_HEADER_VALUE_START:
                # Skip leading spaces.
                if ch != SPACE:
                    # Mark the start of the header value.
                    self.header_value_pos = idx
                    idx -= 1
                    # Move to the header-value state, reprocessing this character.
                    state = STATE_HEADER_VALUE

            elif state == STATE_HEADER_VALUE:
                # If we've got a CR, we're nearly done our headers.  Otherwise,
                # we do nothing and just move past this character.
                if ch == CR:
                    if self.header_value_pos != -1:
                        self.callback('header_value', data, self.header_value_pos, idx)
                        self.header_value_pos = -1

                    self.callback('header_end', b'', 0, 0)
                    state = STATE_HEADER_VALUE_ALMOST_DONE

            elif state == STATE_HEADER_VALUE_ALMOST_DONE:
                # The last character should be a LF.  If not, it's an error.
                if ch != LF:
                    raise ValueError(f"Did not find \\n at end of header (found {chr(ch)})")

                # Move back to the start of another header.  Note that if that
                # state detects ANOTHER newline, it'll trigger the end of our
                # headers.
                state = STATE_HEADER_FIELD_START

            elif state == STATE_HEADERS_ALMOST_DONE:
                # We're almost done our headers.  This is reached when we parse
                # a CR at the beginning of a header, so our next character
                # should be a LF, or it's an error.
                if ch != LF:
                    raise ValueError(f"Did not find \\n at end of headers (found {chr(ch)})")

                self.callback('headers_finished', b'', 0, 0)
                # Mark the start of our part data.
                self.part_data_pos = idx + 1
                state = STATE_PART_DATA

            elif state == STATE_PART_DATA:
                # We're processing our part data right now.  During this, we
                # need to efficiently search for our boundary, since any data
                # on any number of lines can be a part of the current data.
                # We use the Boyer-Moore-Horspool algorithm to efficiently
                # search through the remainder of the buffer looking for our
                # boundary.

                # Save the current value of our index.  We use this in case we
                # find part of a boundary, but it doesn't match fully.
                prev_index = index

                # Set up variables.
                boundary_end = boundary_len - 1
                boundary_chars = self.boundary_chars

                # If our index is 0, we're starting a new part, so start our
                # search.
                if index == 0:
                    # Search forward until we either hit the end of our buffer,
                    # or reach a character that's in our boundary.
                    idx += boundary_end
                    while idx < data_len - 1 and data[idx] not in boundary_chars:
                        idx += boundary_len

                    # Reset i back the length of our boundary, which is the
                    # earliest possible location that could be our match (i.e.
                    # if we've just broken out of our loop since we saw the
                    # last character in our boundary)
                    idx -= boundary_end
                    ch = data[idx]

                # Now, we have a couple of cases here.  If our index is before
                # the end of the boundary...
                if index < boundary_len:
                    # If the character matches...
                    if boundary[index] == ch:
                        # If we found a match for our boundary, we send the
                        # existing data.
                        if index == 0 and self.part_data_pos != -1:
                            self.callback('part_data', data, self.part_data_pos, idx)
                            self.part_data_pos = -1

                        # The current character matches, so continue!
                        index += 1
                    else:
                        index = 0

                # Our index is equal to the length of our boundary!
                elif index == boundary_len:
                    # First we increment it.
                    index += 1

                    # Now, if we've reached a newline, we need to set this as
                    # the potential end of our boundary.
                    if ch == CR:
                        flags |= FLAG_PART_BOUNDARY

                    # Otherwise, if this is a hyphen, we might be at the last
                    # of all boundaries.
                    elif ch == HYPHEN:
                        flags |= FLAG_LAST_BOUNDARY

                    # Otherwise, we reset our index, since this isn't either a
                    # newline or a hyphen.
                    else:
                        index = 0

                # Our index is right after the part boundary, which should be
                # a LF.
                elif index == boundary_len + 1:
                    # If we're at a part boundary (i.e. we've seen a CR
                    # character already)...
                    if flags & FLAG_PART_BOUNDARY:
                        # We need a LF character next.
                        if ch == LF:
                            # Unset the part boundary flag.
                            flags &= (~FLAG_PART_BOUNDARY)

                            # Callback indicating that we've reached the end of
                            # a part, and are starting a new one.
                            self.callback('part_end', b'', 0, 0)
                            self.callback('part_begin', b'', 0, 0)

                            # Move to parsing new headers.
                            index = 0
                            state = STATE_HEADER_FIELD_START
                            idx += 1
                            continue

                        # We didn't find an LF character, so no match.  Reset
                        # our index and clear our flag.
                        index = 0
                        flags &= (~FLAG_PART_BOUNDARY)

                    # Otherwise, if we're at the last boundary (i.e. we've
                    # seen a hyphen already)...
                    elif flags & FLAG_LAST_BOUNDARY:
                        # We need a second hyphen here.
                        if ch == HYPHEN:
                            # Callback to end the current part, and then the
                            # message.
                            self.callback('part_end', b'', 0, 0)
                            self.callback('end', b'', 0, 0)
                            state = STATE_END
                        else:
                            # No match, so reset index.
                            index = 0

                # If we have an index, we need to keep this byte for later, in
                # case we can't match the full boundary.
                if index > 0:
                    self.lookbehind[index - 1] = ch

                # Otherwise, our index is 0.  If the previous index is not, it
                # means we reset something, and we need to take the data we
                # thought was part of our boundary and send it along as actual
                # data.
                elif prev_index > 0:
                    # Callback to write the saved data.
                    lb_data = bytes(self.lookbehind)
                    self.callback('part_data', lb_data, 0, prev_index)

                    # Overwrite our previous index.
                    prev_index = 0

                    # Re-set our mark for part data.
                    self.part_data_pos = idx

                    # Re-consider the current character, since this could be
                    # the start of the boundary itself.
                    idx -= 1

            elif state == STATE_START:
                # Skip leading newlines
                if not (ch == CR or ch == LF):

                    # Move to the next state, but decrement i so that we re-process
                    # this character.
                    idx -= 1
                    state = STATE_START_BOUNDARY

            elif state == STATE_END:
                # Do nothing and just consume a byte in the end state.
                pass

            else:
                raise ValueError(f"Reached an unknown state {state} at {idx}")

            # Move to the next byte.
            idx += 1

        if self.header_field_pos != -1:
            self.callback('header_field', data, self.header_field_pos, data_len)
            self.header_field_pos = 0

        if self.header_value_pos != -1:
            self.callback('header_value', data, self.header_value_pos, data_len)
            self.header_value_pos = 0

        if self.part_data_pos != -1:
            self.callback('part_data', data, self.part_data_pos, data_len)
            self.part_data_pos = 0

        self.index = index
        self.state = state
        self.flags = flags
        self.cursize += data_len


def prune_data(data_len: int, cursize: int, max_size: int) -> int:
    if max_size and (cursize + data_len) > max_size:
        data_len = max_size - cursize

    return data_len


#  pylama:ignore=D,E221
