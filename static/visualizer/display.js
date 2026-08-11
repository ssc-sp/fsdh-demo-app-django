var mapMin = 0;
var initGuess = false;
var histo = {
    width: 1000,
    height: 300,
    buffer: 20,
};

const params = new URLSearchParams(document.location.search);
const rawmap = {};

// The function that gets called once the FITS file has loaded.
// Handles most things from the initial prep to the drawing to the cavases (observation adn graph.)
var callback = function() {
    const canvas = document.getElementById("obs-canvas");
    const ctx = canvas.getContext("2d");
    const dark_range = document.getElementById("dark");
    const light_range = document.getElementById("light");

    var header = this.getHeader();
    var data = this.getDataUnit();

    const width = header.get('NAXIS1'); // get image width
    const height = header.get('NAXIS2'); // get image height

    curObs = header.get('PRODUCT');

    //Draw the image
    const imgData = ctx.createImageData(width, height);
    data.getFrame(0, (pixels) => {
        // Values that only need to be calculated at the start.
        if (!initGuess) {
            initOnly(header, pixels)
            initGuess = true;
        }

        const range = light_range.value - dark_range.value;

        // Paint the pixels.
        for (var i = 0; i < pixels.length; i++) {
            var value = ((pixels[i] - dark_range.value) / range) * 255;

            imgData.data[i*4 + 0] = value;
            imgData.data[i*4 + 1] = value;
            imgData.data[i*4 + 2] = value;
            imgData.data[i*4 + 3] = 255;
        };

        // Load the image onto the canvas.
        canvas.width = width;
        canvas.height = height;
        ctx.putImageData(imgData, 0, 0);

        // Histogram time.
        histo.width = width - 250;
        histogram()
    })
}

// The data that only needs to be created/used at the start.
// Includes the black/white options and initial values, light map data and the header list details.
function initOnly(header, pixels) {
    const dark_range = document.getElementById("dark");
    const light_range = document.getElementById("light");
    const totminmax = FITS.ImageUtils.getExtent(pixels);
    mapMin = totminmax[0];
    dark_range.min = totminmax[0];
    dark_range.max = totminmax[1];
    light_range.min = totminmax[0];
    light_range.max = totminmax[1];

    // Calculate the light map data.
    for (var i = 0; i < pixels.length; i++) {
        if (rawmap[parseInt(pixels[i]) - mapMin]) rawmap[parseInt(pixels[i]) - mapMin] = rawmap[parseInt(pixels[i]) - mapMin]+1;
        else rawmap[parseInt(pixels[i]) - mapMin] = 1;
    };
    guesstimateBW();

    // Create the header details list
    const info_list = document.getElementById("info-list");
    Object.entries(header.cards).forEach(([key, value]) => {
        if (value.value || value.comment) {
            var item = document.createElement("li");
            var str = key + ": " + value.value;
            if (value.comment) str += " /" + value.comment;
            item.append(str);
            info_list.appendChild(item);
        }
    });

    const canvas = document.getElementById("histogram");
    const ctx = canvas.getContext("2d");
    const style = window.getComputedStyle(canvas);
    const bx = parseInt(style.getPropertyValue("border-left-width"));
    const by = parseInt(style.getPropertyValue("border-top-width"));
    canvas.addEventListener("click", (event) => { //mousemove
        const x = event.clientX - canvas.getBoundingClientRect().left;
        const y = event.clientY - canvas.getBoundingClientRect().top;

        histogram();
        
        ctx.fillStyle = "blue";
        ctx.fillRect(x-bx, 0, 1, canvas.height-histo.buffer);
        const values = Object.entries(rawmap);
        var ind = parseInt((x-bx)*values.length/canvas.width);
        if (ind >= 0 && ind < values.length) document.getElementById("histogram-highlight").innerText = "Level "+(parseInt(values[ind][0])+mapMin)+": "+values[ind][1]+" pixels.";
    });
}

// Tries to guess/estimate appropriate values for black and white pixels.
// Black will be set to the most common value.
// White will be set so that only the highest 0.1% of pixels are that colour.
function guesstimateBW() {
    const values = Object.entries(rawmap);
    const dark_range = document.getElementById("dark");
    const light_range = document.getElementById("light");

    var tot = 0; // Total pixel count.
    var peak = [0, 0]; // The light value with the most pixels. [value, count]
    for (let i = 0; i < values.length; i++) {
        // Finds the total.
        tot += values[i][1];
        // Updates the peak if a new one is found.
        if (values[i][1] >= peak[1]) {
            peak = [values[i][0], values[i][1]];
        }
    }
    dark_range.value = parseInt(peak[0]) + mapMin;

    var light_guess = tot;
    for (let i = values.length-1; i >= 0; i--) {
        light_guess -= values[i][1];
        if (light_guess <= tot * 0.999) {
            light_range.value = parseInt(values[i][0]) + mapMin;
            break;
        }
    }
}

// Draws the light histogram
function histogram() {
    const canvas = document.getElementById("histogram");
    const ctx = canvas.getContext("2d");
    const values = Object.entries(rawmap);
    const dark_range = document.getElementById("dark");
    const light_range = document.getElementById("light");

    // Dimensions
    canvas.width = histo.width;
    canvas.height = histo.height;
    const buffer = histo.buffer;

    // Maximum pixel count of light level.
    var max = 0;
    for (let i = 0; i < values.length; i++) {
        if (max < values[i][1]) max = values[i][1];
    }

    // Bar queue
    var queue = []
    
    // Trace graph
    var tickCount = 24;
    ctx.beginPath();
    ctx.moveTo(0, canvas.height-buffer);
    for (let i = 0; i < values.length; i++) {
        ctx.lineTo(i*canvas.width/values.length, canvas.height-(values[i][1]*(canvas.height-buffer)/max)-buffer);
        // Current level text & tick
        if (i % (2*Math.floor(values.length/tickCount)) == 0) ctx.fillText(parseInt(values[i][0])+mapMin, (i*canvas.width/values.length)+2, canvas.height-1)
        if (i % (2*Math.floor(values.length/tickCount)) == Math.floor(values.length/tickCount)) ctx.fillText(parseInt(values[i][0])+mapMin, (i*canvas.width/values.length)+2, canvas.height-Math.floor(histo.buffer/2)-1)
        if (i % Math.floor(values.length/tickCount) == 0) ctx.fillRect(i*canvas.width/values.length, canvas.height-buffer, 1, buffer);

        // Add to queue the bars for the dark & light zones.
        if (i+1 < values.length && ((parseInt(values[i][0]) <= dark_range.value-mapMin && parseInt(values[i+1][0]) > dark_range.value-mapMin)
                                || (parseInt(values[i][0]) <= light_range.value-mapMin && parseInt(values[i+1][0]) > light_range.value-mapMin))) {
            queue.push(i*canvas.width/values.length);
        }
    }
    ctx.closePath();
    ctx.fill();

    // Draw the queued bars
    ctx.fillStyle = "red";
    queue.forEach(pos => {
        ctx.fillRect(pos, 0, 1, canvas.height-buffer);
    })
}